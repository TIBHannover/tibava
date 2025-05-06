from typing import Dict, List
import logging

from ..utils.analyser_client import TaskAnalyserClient

from backend.models import PluginRun, PluginRunResult, Video, Timeline
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from backend.utils.parser import Parser
from backend.utils.task import Task

from data import DataManager
from django.db import transaction

from django.conf import settings


@PluginManager.export_parser("x_clip")
class XCLIPParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "x_clip"},
            "search_term": {"parser": str, "required": True},
            "fps": {"parser": float, "default": 2.0},
        }


@PluginManager.export_plugin("x_clip")
class XCLIP(Task):
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
            "x_clip_video_embedding",
            parameters={"fps": parameters.get("fps")},
            inputs={"video": video_id},
            outputs=["image_features", "video_features"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.3
            plugin_run.save()

        if result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "x_clip_probs",
            parameters={"search_term": parameters.get("search_term")},
            inputs={**result[0]},
            outputs=["probs"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.6
            plugin_run.save()

        if result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "min_max_norm",
            inputs={"scalar": result[0]["probs"]},
            downloads=["scalar"],
        )
        if result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with result[1]["scalar"] as d:
                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=d.id,
                    name="x_clip",
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
                    "timelines": {"scalar": timeline_db.id.hex},
                    "data": {"scalar": result[1]["scalar"].id},
                }
