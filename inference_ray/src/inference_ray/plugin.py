import logging
import os
import re
from typing import Dict, List, Any, Type, Callable

import importlib
import json
import requests
import uuid

from utils import convert_name
from utils.plugin import Plugin, Manager
from data import Data, DataManager

from packaging import version
from typing import Union, Dict, Any

# from analyser.inference.callback import AnalyserPluginCallback


def convert_name(name):
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class AnalyserPluginCallback:
    def update(self, **kwargs):
        pass


class AnalyserProgressCallback(AnalyserPluginCallback):
    def __init__(self, shared_memory) -> None:
        self.shared_memory = shared_memory

    def update(self, progress=0.0, **kwargs):
        self.shared_memory["progress"] = progress


class AnalyserPlugin(Plugin):
    @classmethod
    def __init_subclass__(
        cls,
        parameters: Dict[str, Any] = None,
        requires: Dict[str, Type[Data]] = None,
        provides: Dict[str, Type[Data]] = None,
        **kwargs,
    ):
        super().__init_subclass__(**kwargs)
        cls._requires = requires
        cls._provides = provides
        cls._parameters = parameters
        cls._name = convert_name(cls.__name__)

    def __init__(self, config: Dict = None):
        self._config = self._default_config
        if config is not None:
            self._config.update(config)

    @classmethod
    @property
    def requires(cls):
        return cls._requires

    @classmethod
    @property
    def provides(cls):
        return cls._provides

    @classmethod
    def update_callbacks(cls, callbacks: List[AnalyserPluginCallback], **kwargs):
        if callbacks is None or not isinstance(callbacks, (list, set)):
            return
        for x in callbacks:
            x.update(**kwargs)

    def __call__(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        input_parameters = self._parameters
        if parameters is not None:
            input_parameters.update(parameters)
        logging.info(f"[Plugin] {self._name} starting")

        result = self.call(inputs, data_manager, input_parameters, callbacks=callbacks)

        logging.info(f"[Plugin] {self._name} done")
        return result


class AnalyserPluginManager(Manager):
    _plugins = {}

    def __init__(self, config: Dict = None, **kwargs):
        super().__init__(config, **kwargs)
        self.config = config
        if not self.config:
            self.config = {}

        if (
            self.config.get("status_port") is None
            or self.config.get("status_port") == ""
        ):
            self.status_base_url = f"http://{self.config.get('host')}"
        else:
            self.status_base_url = (
                f"http://{self.config.get('host')}:{self.config.get('status_port')}"
            )

        if self.config.get("port") is None or self.config.get("port") == "":
            self.base_url = f"http://{self.config.get('host')}"
        else:
            self.base_url = (
                f"http://{self.config.get('host')}:{self.config.get('port')}"
            )
        self.find()
        self.plugin_list = []

        # logging.error(self.plugin_list)

    @classmethod
    def export(cls, name):
        def export_helper(plugin):
            cls._plugins[name] = plugin
            return plugin

        return export_helper

    # TODO I am not sure if this is fine here

    def plugin_status(self):
        print(f"{self.status_base_url}/api/serve/applications/", flush=True)
        try:
            status = requests.get(
                f"{self.status_base_url}/api/serve/applications/"
            ).json()
        except:
            logging.error("AnalyserPluginMananger: Can get status from ray server")
            return []

        running_model_map = {}
        for _, app in status.get("applications", {}).items():
            model_name = (
                app.get("deployed_app_config", {}).get("args", {}).get("model", "")
            )
            route = app.get("deployed_app_config", {}).get("route_prefix", "")
            is_running = app.get("status", "DEPLOY_FAILED") == "RUNNING"
            if model_name in running_model_map:
                logging.warning(
                    f"The same plugin is running several times {model_name}"
                )
            running_model_map[model_name] = {
                "plugin": model_name,
                "route": route,
                "is_running": is_running,
            }

        for name, plugin_cls in self._plugins.items():
            if name not in running_model_map:
                logging.warning(f"Plugin {name} is not running")
                continue
            running_model_map[name].update(
                {
                    "requires": plugin_cls.requires,
                    "provides": plugin_cls.provides,
                    "version": plugin_cls.version,
                }
            )

        return list(running_model_map.values())

    def plugins(self):
        return self._plugins

    def find(self, path=None):
        if path is None:
            path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "plugins")
        file_re = re.compile(r"(.+?)\.py$")
        for pl in os.listdir(path):
            match = re.match(file_re, pl)
            if match:
                importlib.import_module(
                    "inference_ray.plugins.{}".format(match.group(1))
                )

    def build_plugin(self, plugin: str, config: Dict = None) -> AnalyserPlugin:
        if plugin not in self._plugins:
            return None
        plugin_to_run = None
        for plugin_name, plugin_cls in self._plugins.items():
            if plugin_name == plugin:
                plugin_to_run = plugin_cls

        if plugin_to_run is None:
            logging.error(f"[AnalyserPluginManager] plugin: {plugin} not found")
            return None

        return plugin_to_run(config)

    def __call__(
        self,
        plugin: str,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ):
        plugins = {x["plugin"]: x for x in self.plugin_status()}

        if plugin not in plugins:
            logging.error(f"[AnalyserPluginManager] plugin: {plugin} not found")
            return None

        plugin_to_run = plugins[plugin]

        print(f"{self.base_url}{plugin_to_run['route']}", flush=True)
        try:
            results = requests.post(
                f"{self.base_url}{plugin_to_run['route']}",
                json={
                    "inputs": {x: y.id for x, y in inputs.items()},
                    "parameters": parameters,
                },
            )
        except:
            logging.error("AnalyserPluginMananger: Can start plugin on ray server")
            return []

        try:
            data = results.json()
        except:
            logging.error(f"AnalyserPluginMananger: {results}")
            logging.error("AnalyserPluginMananger: Can decode response from ray server")
            return []

        return data
