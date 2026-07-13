import importlib
import os
import re
import logging

from analyser.utils.plugin.manager import Manager
from analyser.utils.plugin.plugin import Plugin
from analyser.utils.plugin.factory import Factory

# from analyser.inference import InferenceServerFactory

from packaging import version
from typing import Any, Dict, Type
from analyser.utils import convert_name

from tibava_interface import common_pb2


from inference import InferenceServerManager


class ComputePluginResult:
    def __init__(self, plugin, entries, annotations):
        self._plugin = plugin
        self._entries = entries
        self._annotations = annotations
        assert len(self._entries) == len(self._annotations)

    def __repr__(self):
        return f"{self._plugin} {self._annotations}"


class ComputePlugin(Plugin):
    @classmethod
    def __init_subclass__(
        cls,
        parameters: Dict[str, Any] = None,
        # requires: Dict[str, Type[Data]] = None,
        # provides: Dict[str, Type[Data]] = None,
        requires: Dict[str, Type] = None,
        provides: Dict[str, Type] = None,
        **kwargs,
    ):
        super().__init_subclass__(**kwargs)
        cls.requires = requires
        cls.provides = provides
        cls.parameters = parameters
        cls.cls_name = convert_name(cls.__name__)

    def __init__(
        self,
        compute_plugin_manager: "ComputePluginManager",
        inference_server_manager: "InferenceServerManager",
        instance_name: str,
        config: Dict = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._compute_plugin_manager = compute_plugin_manager
        self._inference_server_manager = inference_server_manager
        self._config = self._default_config
        self.instance_name = instance_name
        if config is not None:
            self._config.update(config)

    @property
    def compute_plugin_manager(self):
        return self._compute_plugin_manager

    @property
    def inference_server_manager(self):
        return self._inference_server_manager

    @staticmethod
    def map_analyser_request_to_dict(request):
        input_dict = {}
        for input in request.inputs:
            if input.name not in input_dict:
                input_dict[input.name] = []
            # logging.error(input)
            if input.WhichOneof("data") == "image":
                input_dict[input.name].append(
                    {"type": "image", "content": input.image.content}
                )
            if input.WhichOneof("data") == "text":
                input_dict[input.name].append(
                    {"type": "text", "content": input.text.text}
                )

        parameter_dict = {}
        for parameter in request.parameters:
            if parameter.name not in parameter_dict:
                parameter_dict[parameter.name] = []
            # TODO convert datatype
            if parameter.type == common_pb2.FLOAT_TYPE:
                parameter_dict[parameter.name] = float(
                    parameter.content.decode("utf-8")
                )
            if parameter.type == common_pb2.INT_TYPE:
                parameter_dict[parameter.name] = int(parameter.content.decode("utf-8"))
            if parameter.type == common_pb2.STRING_TYPE:
                parameter_dict[parameter.name] = str(parameter.content.decode("utf-8"))
            if parameter.type == common_pb2.BOOL_TYPE:
                parameter_dict[parameter.name] = bool(parameter.content.decode("utf-8"))

        return input_dict, parameter_dict

    @staticmethod
    def map_dict_to_analyser_request(inputs, parameters):
        request = common_pb2.PluginRun()
        for key, values in inputs.items():
            for value in values:
                input_field = request.inputs.add()
                if value["type"] == "image":
                    input_field.name = "image"
                    if "path" in value:
                        input_field.image.content = open(value["path"], "rb").read()
                    elif "content" in value:
                        input_field.image.content = value["content"]
                    else:
                        logging.error("Missing image content")

                elif value["type"] == "text":
                    input_field.name = "text"
                    input_field.text.text = value["content"]

        for key, value in parameters.items():
            parameter = request.parameters.add()
            parameter.name = key
            parameter.content = str(value).encode()

            if isinstance(value, float):
                parameter.type = common_pb2.FLOAT_TYPE
            if isinstance(value, int):
                parameter.type = common_pb2.INT_TYPE
            if isinstance(value, str):
                parameter.type = common_pb2.STRING_TYPE

        return request

    def __call__(self, plugin_run: common_pb2.PluginRun) -> ComputePluginResult:
        return self.call(plugin_run)


class ComputePluginFactory(
    Factory,
    plugins_path=os.path.join(os.path.abspath(os.path.dirname(__file__)), "compute"),
    plugin_import_path="analyser.plugins.compute",
    plugin_cls=ComputePlugin,
):
    pass


class ComputePluginManager:
    def __init__(
        self,
        config: Dict,
        inference_server_manager: "InferenceServerManager",
        compute_plugin_factory: ComputePluginFactory = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.config = config

        if compute_plugin_factory is None:
            compute_plugin_factory = ComputePluginFactory()

        self.compute_plugin_factory = compute_plugin_factory
        self.inference_server_manager = inference_server_manager

        self.compute_plugins = {}
        for plugin in self.config.get("compute_plugin", []):
            plugin_name = plugin.get("name")
            if plugin_name is None and not isinstance(plugin_name, str):
                # logging.error(
                #     "Inference server has no name field or it is not a string."
                # )
                exit(-1)

            plugin_type = plugin.get("type")
            if plugin_type is None and not isinstance(plugin_type, str):
                logging.error(
                    "Inference server has no name field or it is not a string."
                )
                exit(-1)

            compute_plugin_inference_server_name = plugin.get("inference")
            if not isinstance(compute_plugin_inference_server_name, (str, type(None))):
                logging.error(
                    f'Compute plugin "{plugin_name}" has a invalid inference type.'
                )
                exit(-1)

            compute_plugin = compute_plugin_factory.build(
                plugin_type,
                config=plugin.get("params", {}),
                instance_name=plugin_name,
                compute_plugin_manager=self,
                inference_server_manager=inference_server_manager,
            )

            if compute_plugin_inference_server_name is not None:
                logging.info("register_compute_plugin")
                inference_server_manager.register_compute_plugin(
                    compute_plugin_inference_server_name, compute_plugin
                )

            self.compute_plugins[plugin_name] = {
                "compute_plugin": compute_plugin,
                "config": plugin,
                "inference_server_name": compute_plugin_inference_server_name,
            }

    def __iter__(self):
        yield from self.compute_plugins.items()

    def __getitem__(self, compute_plugin_name: str):
        return self.compute_plugins[compute_plugin_name]

    def __call__(self, compute_plugin_name: str):
        pass
