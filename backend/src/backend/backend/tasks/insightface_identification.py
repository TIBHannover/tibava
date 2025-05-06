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


@PluginManager.export_parser("insightface_identification")
class InsightfaceIdentificationParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Face Identification"},
            "fps": {"parser": float, "default": 2},
            "query_images": {"parser": str},
            "normalize": {"parser": float, "default": 1},
            "normalize_min_val": {"parser": float, "default": 0.3},
            "normalize_max_val": {"parser": float, "default": 1.0},
        }


@PluginManager.export_plugin("insightface_identification")
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

        # query image path
        if parameters.get("embedding_ref") == None:
            # load query image
            image_data = manager.create_data("ImagesData")
            with image_data:
                image_path = parameters.get("query_images")
                image = iio.imread(image_path)
                image_data.save_image(image)

            query_image_id = client.upload_data(image_data)

            # query image face detection
            facedetection_result = self.run_analyser(
                client,
                "insightface_image_detector_torch",
                inputs={"images": query_image_id},
                outputs=["kpss", "faces"],
            )

            if plugin_run is not None:
                plugin_run.progress = 0.1
                plugin_run.save()

            if facedetection_result is None:
                raise Exception

            # feature extraction of faces
            query_image_feature_result = self.run_analyser(
                client,
                "insightface_image_feature_extractor",
                inputs={
                    "images": query_image_id,
                    "kpss": facedetection_result[0]["kpss"],
                    "faces": facedetection_result[0]["faces"],
                },
                outputs=["features"],
            )

            if plugin_run is not None:
                plugin_run.progress = 0.2
                plugin_run.save()

            if query_image_feature_result is None:
                raise Exception

        # face detection on video
        video_facedetection = self.run_analyser(
            client,
            "insightface_video_detector_torch",
            parameters={
                "fps": parameters.get("fps"),
            },
            inputs={"video": video_id},
            outputs=["kpss", "faces"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.4
            plugin_run.save()

        if video_facedetection is None:
            raise Exception

        video_feature_result = self.run_analyser(
            client,
            "insightface_video_feature_extractor",
            inputs={"video": video_id, "kpss": video_facedetection[0]["kpss"]},
            outputs=["features"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.6
            plugin_run.save()

        if video_feature_result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "cosine_similarity",
            parameters={
                "normalize": 1,
                "index": parameters.get("index"),
            },
            inputs={
                "target_features": video_feature_result[0]["features"],
                "query_features": query_image_feature_result[0]["features"],
            },
            outputs=["probs"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.8
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
                    "data": {
                        "annotations": aggregated_result[1]["aggregated_scalar"].id
                    },
                }
