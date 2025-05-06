from typing import Dict, List
import logging
from backend.models import PluginRun, PluginRunResult, Video, Timeline, TimelineSegment
from backend.plugin_manager import PluginManager

from data import DataManager

from backend.utils.parser import Parser
from backend.utils.task import Task


from ..utils.analyser_client import TaskAnalyserClient
from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("color_analysis")
class ColorAnalyserParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Color Analysis"},
            "k": {"parser": int, "default": 4},
            "fps": {"parser": float, "default": 2.0},
            "max_resolution": {"parser": int, "default": 48},
            "max_iter": {"parser": int, "default": 10},
            "timeline_visualization": {"parser": int, "default": 0},
        }


@PluginManager.export_plugin("color_analysis")
class ColorAnalyser(Task):
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
            "color_analyser",
            parameters={
                "fps": parameters.get("fps"),
                "k": parameters.get("k"),
                "max_resolution": parameters.get("max_resolution"),
                "max_iter": parameters.get("max_iter"),
            },
            inputs={"video": video_id},
            downloads=["colors"],
        )

        if result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with result[1]["colors"] as data:
                data.extract_all(manager)
                parent_timeline = None
                if len(data.data) > 1:
                    parent_timeline = Timeline.objects.create(
                        video=video,
                        name=parameters.get("timeline"),
                        type=Timeline.TYPE_PLUGIN_RESULT,
                    )

                result_timelines = {}
                plugin_run_results = []
                for i, d in enumerate(data.data):
                    plugin_run_result_db = PluginRunResult.objects.create(
                        plugin_run=plugin_run,
                        data_id=d,
                        name="color_analysis",
                        type=PluginRunResult.TYPE_RGB_HIST,
                    )

                    timeline_db = Timeline.objects.create(
                        video=video,
                        name=(
                            parameters.get("timeline") + f" #{i}"
                            if len(data.data) > 1
                            else parameters.get("timeline")
                        ),
                        type=Timeline.TYPE_PLUGIN_RESULT,
                        plugin_run_result=plugin_run_result_db,
                        visualization=Timeline.VISUALIZATION_COLOR,
                        parent=parent_timeline,
                    )

                    result_timelines[i] = timeline_db.id.hex
                    plugin_run_results.append(plugin_run_result_db.id.hex)

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": plugin_run_results,
                    "timelines": result_timelines,
                    "data": {"colors": result[1]["colors"].id},
                }
