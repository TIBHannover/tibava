import logging
from typing import Dict, List

from celery import shared_task

from backend.models import (
    Annotation,
    AnnotationCategory,
    PluginRun,
    PluginRunResult,
    Video,
    TibavaUser,
    Timeline,
    TimelineSegment,
    TimelineSegmentAnnotation,
)
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from ..utils.analyser_client import TaskAnalyserClient
from tibava_data import Shot, ShotsData

from tibava_data import DataManager
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction
from django.conf import settings


logger = logging.getLogger(__name__)


@PluginManager.export_parser("movie_pattern_frameshare")
class MoviePatternFrameshareParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Camera Setting"},
            "fps": {"parser": float, "default": 2.0},
            "shot_timeline_id": {},
            "min_length": {"parser": int, "default": 3},
            # clustering-specific params
            "clustering_method": {"parser": str, "default": "DBScan"},
            "cluster_threshold": {
                "parser": float,
                "default": 0.5,
            },  # agglomerative, dbscan
            "metric": {"parser": str, "default": "cosine"},  # dbscan
            # other params
            "max_samples_per_cluster": {"parser": int, "default": 30},
            "max_cluster": {"parser": int, "default": 50},
            "min_face_height": {"parser": float, "default": 0.1},
        }


@PluginManager.export_plugin("movie_pattern_frameshare")
class MoviePatternFrameshare(Task):
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
        # parameters["fps"] = 0.05

        manager = DataManager(self.config["output_path"])
        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )
        # upload all data
        video_id = self.upload_video(client, video)

        shots_id = None
        if parameters.get("shot_timeline_id"):
            shot_timeline_segments = TimelineSegment.objects.filter(
                timeline__id=parameters.get("shot_timeline_id")
            )
            shots = manager.create_data("ShotsData")
            with shots:
                for x in shot_timeline_segments:
                    shots.shots.append(Shot(start=x.start, end=x.end))
            shots_id = client.upload_data(shots)

        # start plugins

        facedetector_result = self.run_analyser(
            client,
            "insightface_video_detector_torch",
            parameters={
                "fps": parameters.get("fps"),
            },
            inputs={"video": video_id},
            outputs=["images", "kpss", "faces", "bboxes"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.75
            plugin_run.save()

        face_size_filter_result = self.run_analyser(
            client,
            "face_size_filter",
            parameters={
                "min_face_height": parameters.get("min_face_height"),
            },
            inputs=facedetector_result[0],
            outputs=["images", "kpss", "faces", "bboxes"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.4
            plugin_run.save()

        if face_size_filter_result is None:
            raise Exception

        # create image embeddings
        image_feature_result = self.run_analyser(
            client,
            "insightface_video_feature_extractor",
            inputs={
                "video": video_id,
                "kpss": face_size_filter_result[0]["kpss"],
                "faces": face_size_filter_result[0]["faces"],
            },
            outputs=["features"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.6
            plugin_run.save()

        if image_feature_result is None:
            raise Exception

        # cluster faces
        if parameters.get("clustering_method").lower() == "agglomerative":
            cluster_result = self.run_analyser(
                client,
                "clustering",
                parameters={
                    "cluster_threshold": parameters.get("cluster_threshold"),
                    "max_samples_per_cluster": parameters.get(
                        "max_samples_per_cluster"
                    ),
                },
                inputs={
                    "embeddings": image_feature_result[0]["features"],
                },
                outputs=["cluster_data"],
                downloads=["cluster_data"],
            )
        elif parameters.get("clustering_method").lower() == "dbscan":
            cluster_result = self.run_analyser(
                client,
                "dbscanclustering",
                parameters={
                    "cluster_threshold": parameters.get("cluster_threshold"),
                    "metric": parameters.get("metric"),
                    "max_samples_per_cluster": parameters.get(
                        "max_samples_per_cluster"
                    ),
                },
                inputs={
                    "embeddings": image_feature_result[0]["features"],
                },
                outputs=["cluster_data"],
                downloads=["cluster_data"],
            )
        else:
            raise Exception

        if plugin_run is not None:
            plugin_run.progress = 0.8
            plugin_run.save()

        if cluster_result is None:
            raise Exception

        movie_pattern_frameshare = self.run_analyser(
            client,
            "movie_pattern_frameshare",
            inputs={
                "faces": face_size_filter_result[0]["faces"],
                "bboxes": face_size_filter_result[0]["bboxes"],
                "cluster_data": cluster_result[0]["cluster_data"],
                "embeddings": image_feature_result[0]["features"],
                "shots": shots_id,
            },
            downloads=["frameshare"],
        )
        if movie_pattern_frameshare is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with movie_pattern_frameshare[1]["frameshare"] as data:
                annotation_timeline_db = Timeline.objects.create(
                    video=video,
                    name=parameters["timeline"],
                    type=Timeline.TYPE_ANNOTATION,
                )

                category_db, _ = AnnotationCategory.objects.get_or_create(
                    name="Frameshare", video=video, owner=user
                )

                for annotation in data.annotations:
                    timeline_segment_db = TimelineSegment.objects.create(
                        timeline=annotation_timeline_db,
                        start=annotation.start,
                        end=annotation.end,
                    )
                    for label in annotation.labels:
                        label = str(label)
                        if len(label) > settings.ANNOTATION_MAX_LENGTH:
                            label = (
                                label[: max(0, settings.ANNOTATION_MAX_LENGTH - 4)]
                                + " ..."
                            )
                        annotation_db, _ = Annotation.objects.get_or_create(
                            name=label,
                            video=video,
                            category=category_db,
                            owner=user,
                        )

                        TimelineSegmentAnnotation.objects.create(
                            annotation=annotation_db,
                            timeline_segment=timeline_segment_db,
                        )
                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [],
                    "timelines": {"annotations": annotation_timeline_db.id.hex},
                    "data": {
                        "annotations": movie_pattern_frameshare[1]["frameshare"].id
                    },
                }
