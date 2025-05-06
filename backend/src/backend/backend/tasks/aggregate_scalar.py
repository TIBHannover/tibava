import logging
from typing import Dict, List


from backend.models import (
    PluginRun,
    PluginRunResult,
    Video,
    Timeline,
)
from backend.plugin_manager import PluginManager

from ..utils.analyser_client import TaskAnalyserClient
from data import DataManager, ListData
from backend.utils.parser import Parser
from backend.utils.task import Task

from django.db import transaction
from django.conf import settings


logger = logging.getLogger(__name__)


@PluginManager.export_parser("aggregate_scalar")
class AggregateScalarParser(Parser):
    def __init__(self):
        self.aggregation_lut = {0: "or", 1: "and", 2: "mean", 3: "prod"}
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Aggregated Timeline"},
            "timeline_ids": {"required": True},
            "aggregation": {"parser": lambda x: self.aggregation_lut[x], "default": 0},
        }


@PluginManager.export_plugin("aggregate_scalar")
class AggregateScalar(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": settings.GRPC_HOST,
            "analyser_port": settings.GRPC_PORT,
        }

    def __call__(
        self,
        parameters: Dict,
        video: Video = None,
        plugin_run: PluginRun = None,
        dry_run: bool = False,
        **kwargs,
    ):

        manager = DataManager(self.config["output_path"])
        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )

        timelines = manager.create_data("ListData")

        with timelines:
            for timeline_id in parameters.get("timeline_ids"):
                logger.debug(
                    f"Get probabilities from scalar timeline with id: {timeline_id}"
                )

                timeline_db = Timeline.objects.get(id=timeline_id)
                plugin_data_id = timeline_db.plugin_run_result.data_id

                data = manager.load(plugin_data_id)

                timelines.add_data(data)

        timelines_id = client.upload_data(timelines)

        result = self.run_analyser(
            client,
            "aggregate_scalar",
            parameters={
                "aggregation": parameters.get("aggregation"),
            },
            inputs={"timelines": timelines_id},
            downloads=["probs"],
        )

        if result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with result[1]["probs"] as data:
                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=data.id,
                    name="aggregate_scalar",
                    type=PluginRunResult.TYPE_SCALAR,  # S stands for SCALAR_DATA
                )
                timeline_db = Timeline.objects.create(
                    video=video,
                    name=parameters.get("timeline"),
                    type=Timeline.TYPE_PLUGIN_RESULT,
                    plugin_run_result=plugin_run_result_db,
                    visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
                )

            return {
                "plugin_run": plugin_run.id.hex,
                "plugin_run_results": [plugin_run_result_db.id.hex],
                "timelines": {"probs": timeline_db.id.hex},
                "data": {"probs": result[1]["probs"].id},
            }
