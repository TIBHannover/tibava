from typing import Dict, List
import imageio.v3 as iio
import logging

from data import DataManager
from backend.models import PluginRun, PluginRunResult, Video, Timeline, TibavaUser
from backend.plugin_manager import PluginManager

from ..utils.analyser_client import TaskAnalyserClient
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("place_identification")
class InsightfaceIdentificationParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Place Identification"},
            "fps": {"parser": float, "default": 2},
            "query_images": {"parser": str},
            "normalize": {"parser": float, "default": 1},
            "normalize_min_val": {"parser": float, "default": 0.3},
            "normalize_max_val": {"parser": float, "default": 1.0},
            "embedding_ref": {"parser": str, "default": None},
            "index": {"parser": str, "default": -1},
            "cluster_id": {"parser": str, "default": -1},
        }


@PluginManager.export_plugin("place_identification")
class InsightfaceIdentification(Task):
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
        user: TibavaUser = None,
        plugin_run: PluginRun = None,
        dry_run: bool = False,
        **kwargs,
    ):
        # Debug
        # parameters["fps"] = 0.1

        # check whether we compare by input embedding or input image
        manager = DataManager(self.config["output_path"])
        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )
        # upload all data
        video_id = self.upload_video(client, video)

        places_result = self.run_analyser(
            client,
            "places_classifier",
            parameters={
                "fps": parameters.get("fps"),
            },
            inputs={"video": video_id},
            outputs=["embeddings"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.3
            plugin_run.save()

        if places_result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "cosine_similarity",
            parameters={
                "normalize": 1,
                "index": parameters.get("index"),
                "cluster_id": parameters.get("cluster_id"),
            },
            inputs={
                "target_features": places_result[0]["embeddings"],
                "query_features": parameters.get("embedding_ref"),
            },
            outputs=["probs"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.6
            plugin_run.save()

        if result is None:
            raise Exception

        aggregated_result = self.run_analyser(
            client,
            "aggregate_scalar_per_time",
            inputs={"scalar": result[0]["probs"]},
            downloads=["aggregated_scalar"],
        )

        if aggregated_result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with aggregated_result[1]["aggregated_scalar"] as data:
                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=data.id,
                    name="face_identification",
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
                    "data": {"annotations": result[1]["aggregated_scalars"].id},
                }
