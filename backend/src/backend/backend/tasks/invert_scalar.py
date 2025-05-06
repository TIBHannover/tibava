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


@PluginManager.export_parser("invert_scalar")
class InvertScalarParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Inverted Timeline"},
            "scalar_timeline_id": {"required": True},
        }


@PluginManager.export_plugin("invert_scalar")
class InvertScalar(Task):
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

        timeline_id = parameters.get("scalar_timeline_id")
        logger.debug(f"Get probabilities from scalar timeline with id: {timeline_id}")

        timeline_db = Timeline.objects.get(id=timeline_id)
        plugin_data_id = timeline_db.plugin_run_result.data_id

        data = manager.load(plugin_data_id)

        input_scalar_timelines_id = client.upload_data(data)

        result = self.run_analyser(
            client,
            "invert_scalar",
            parameters={},
            inputs={"input": input_scalar_timelines_id},
            downloads=["output"],
        )

        if result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with result[1]["output"] as data:
                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=data.id,
                    name="invert_scalar",
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
                "timelines": {"output": timeline_db.id.hex},
                "data": {"output": result[1]["output"].id},
            }
