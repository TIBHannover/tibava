from typing import Dict, List
import logging

from backend.models import (
    PluginRun,
    PluginRunResult,
    Video,
    Timeline,
    TimelineSegment,
)
from backend.plugin_manager import PluginManager


from ..utils.analyser_client import TaskAnalyserClient
from data import Shot, ShotsData

from backend.utils.parser import Parser
from backend.utils.task import Task
from data import DataManager
from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("shot_density")
class ShotDensityParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Shot Density"},
            "bandwidth": {"parser": float, "default": 10},
            "fps": {"parser": float, "default": 10.0},
            "shot_timeline_id": {"required": True},
        }


@PluginManager.export_plugin("shot_density")
class ShotDensity(Task):
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

        shots_id = None
        if parameters.get("shot_timeline_id"):
            shot_timeline_db = Timeline.objects.get(
                id=parameters.get("shot_timeline_id")
            )
            shot_timeline_segments = TimelineSegment.objects.filter(
                timeline=shot_timeline_db
            )

            shots = manager.create_data("ShotsData")
            with shots:
                for x in shot_timeline_segments:
                    shots.shots.append(Shot(start=x.start, end=x.end))
            shots_id = client.upload_data(shots)

        result = self.run_analyser(
            client,
            "shot_density",
            parameters={
                "bandwidth": parameters.get("bandwidth"),
                "fps": parameters.get("fps"),
            },
            inputs={"shots": shots_id},
            downloads=["shot_density"],
        )

        if result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with result[1]["shot_density"] as data:
                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=data.id,
                    name="shot_density",
                    type=PluginRunResult.TYPE_SCALAR,
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
                    "timelines": {"annotations": timeline_db},
                    "data": {"annotations": result[1]["shot_density"].id},
                }
