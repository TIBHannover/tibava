import logging
import re
import importlib
import os
from typing import Dict
import traceback


class Factory:
    _plugins = {}

    @classmethod
    def __init_subclass__(
        cls,
        plugins_path: str = None,
        plugin_import_path: str = None,
        plugin_cls=None,
        **kwargs,
    ):
        super().__init_subclass__(**kwargs)
        cls._plugins_path = plugins_path
        cls._plugin_import_path = plugin_import_path
        cls._plugin_type = plugin_cls

    def __init__(self, **kwargs):
        self.find_and_register_plugins()

    @classmethod
    def export(cls, name: str):

        def export_helper(plugin):
            cls._plugins[name] = plugin
            return plugin

        return export_helper

    def find_and_register_plugins(self, path: str = None):
        if path is None:
            path = self._plugins_path

        file_re = re.compile(r"(.+?)\.py$")

        for pl in os.listdir(path):

            match = re.match(file_re, pl)

            if not match:
                continue

            import_path = f"{self._plugin_import_path}.{match.group(1)}"

            import_result = importlib.import_module(import_path)

    def build(self, name: str, **kwargs):
        if name not in self._plugins:
            logging.error(f'[Factory::build] Unknown plugin: "{name}"')
            return None
        return self._plugins[name](**kwargs)
