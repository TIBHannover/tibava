from typing import Dict, List

from backend.models import PluginRun, PluginRunResult, Video, Timeline, TimelineSegment
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

import logging

from ..utils.analyser_client import TaskAnalyserClient
from data import DataManager
from backend.utils.parser import Parser
from backend.utils.task import Task

from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("color_brightness_analysis")
class ColorBrightnessAnalyserParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Color Brightness"},
            "fps": {"parser": float, "default": 2.0},
            "normalize": {"parser": bool, "default": True},
        }


@PluginManager.export_plugin("color_brightness_analysis")
class ColorBrightnessAnalyser(Task):
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

        video_id = self.upload_video(client, video)
        result = self.run_analyser(
            client,
            "color_brightness_analyser",
            parameters={
                "fps": parameters.get("fps"),
                "normalize": parameters.get("normalize"),
            },
            inputs={"video": video_id},
            downloads=["brightness"],
        )

        if result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with result[1]["brightness"] as data:
                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=data.id,
                    name="color_brightness_analysis",
                    type=PluginRunResult.TYPE_SCALAR,
                )

                timeline_db = Timeline.objects.create(
                    video=video,
                    name=parameters.get("timeline"),
                    type=Timeline.TYPE_PLUGIN_RESULT,
                    plugin_run_result=plugin_run_result_db,
                    visualization=Timeline.VISUALIZATION_SCALAR_LINE,
                )

            return {
                "plugin_run": plugin_run.id.hex,
                "plugin_run_results": [plugin_run_result_db.id.hex],
                "timelines": {"brightness": timeline_db.id.hex},
                "data": {"brightness": result[1]["brightness"].id},
            }
