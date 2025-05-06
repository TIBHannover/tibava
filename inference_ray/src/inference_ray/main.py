import logging
from ray import serve
from typing import Dict
from ray.serve import Application

from data import DataManager
from inference_ray.plugin import AnalyserPluginManager, AnalyserPlugin


@serve.deployment
class Deployment:
    def __init__(self, plugin: AnalyserPlugin, data_manager: DataManager) -> None:
        self.plugin = plugin
        self.data_manager = data_manager

    async def __call__(self, request) -> Dict[str, str]:
        data = await request.json()
        inputs = data.get("inputs")
        parameters = data.get("parameters")
        logging.error("###############")
        logging.error(inputs)
        logging.error(parameters)
        logging.error("###############")

        plugin_inputs = {}
        for name, id in inputs.items():
            data = self.data_manager.load(id)
            plugin_inputs[name] = data

        results = self.plugin(
            plugin_inputs, data_manager=self.data_manager, parameters=parameters
        )

        return {x: y.id for x, y in results.items()}


def app_builder(args) -> Application:
    logging.warning(args)
    data_manager = DataManager(args.get("data_path"))
    manager = AnalyserPluginManager()
    plugin = manager.build_plugin(args.get("model"), args.get("params", {}))

    return Deployment.bind(plugin, data_manager)
