from typing import Dict
import logging
import os

from analyser.utils.plugin import Plugin
from analyser.utils.plugin import Factory


class InferenceServer(Plugin):
    def __init__(self, config: Dict) -> None:
        super().__init__(config)

    def start(self) -> None:
        pass


class InferenceServerFactory(
    Factory,
    plugins_path=os.path.join(
        os.path.abspath(os.path.dirname(__file__)), "inference_plugins"
    ),
    plugin_import_path="analyser.inference.inference_plugins",
    plugin_cls=InferenceServer,
):
    pass


class InferenceServerManager:
    def __init__(
        self, config: Dict, inference_server_factory: InferenceServerFactory = None
    ):
        self.config = config

        if inference_server_factory is None:
            inference_server_factory = InferenceServerFactory()

        self.inference_server_factory = inference_server_factory

        # Build an dict with index name to indexer plugin and config
        self.inference_servers = {}
        for inference in self.config.get("inference", []):

            inference_server_name = inference.get("name")
            if inference_server_name is None and not isinstance(
                inference_server_name, str
            ):
                logging.error(
                    "Inference server has no name field or it is not a string."
                )
                exit(-1)

            inference_server_type = inference.get("type")
            if inference_server_type is None and not isinstance(
                inference_server_type, str
            ):
                # logging.error(
                #     "Inference server has no name field or it is not a string."
                # )
                exit(-1)

            inference_server = inference_server_factory.build(
                inference_server_type, config=inference.get("params", {})
            )
            self.inference_servers[inference_server_name] = {
                "inference_server": inference_server,
                "config": inference,
                "compute_plugins": [],
            }

    def register_compute_plugin(
        self, inference_server_name: str, compute_plugin: "ComputePlugin"
    ):
        if inference_server_name not in self.inference_servers:
            logging.error(f'Unknown inference server "{inference_server_name}"')
            return None

        self.inference_servers[inference_server_name]["compute_plugins"].append(
            compute_plugin
        )

    def start(self):
        for inference_server_entry in self.inference_servers.values():
            inference_server_entry["inference_server"].start(
                inference_server_entry["compute_plugins"]
            )

    def __call__(
        self,
        compute_plugin_manager: "ComputePluginManager",
        compute_plugin_name: str,
        **kwargs,
    ):
        # TODO add more checks here
        compute_plugin = compute_plugin_manager[compute_plugin_name]
        inference_server_name = compute_plugin["inference_server_name"]
        if inference_server_name is None:
            return compute_plugin["compute_plugin"](**kwargs)

        return self.inference_servers[inference_server_name]["inference_server"](
            compute_plugin["compute_plugin"], **kwargs
        )
