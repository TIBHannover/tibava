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


@PluginManager.export_parser("movie_pattern_intensify")
class MoviePatternIntensifyParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Camera Setting"},
            "fps": {"parser": float, "default": 2.0},
            "shot_timeline_id": {},
            "min_length": {"parser": int, "default": 3},
        }


@PluginManager.export_plugin("movie_pattern_intensify")
class MoviePatternIntensify(Task):
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
        manager = DataManager(self.config["output_path"])
        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )

        video_id = self.upload_video(client, video)

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
            "shot_type_classifier",
            inputs={"video": video_id},
            outputs=["probs"],
        )

        if result is None:
            raise Exception

        annotations_result = self.run_analyser(
            client,
            "shot_annotator",
            inputs={"probs": result[0]["probs"], "shots": shots_id},
            outputs=["annotations"],
        )
        if annotations_result is None:
            raise Exception

        movie_pattern_intensify = self.run_analyser(
            client,
            "movie_pattern_intensify",
            inputs={"shot_sizes": annotations_result[0]["annotations"]},
            downloads=["intensify"],
        )
        if movie_pattern_intensify is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        """
        Create timeline(s) with probability of each class as scalar data
        """
        logger.info(
            f" Create scalar color (SC) timeline with probabilities for each class"
        )

        with transaction.atomic():
            with movie_pattern_intensify[1]["intensify"] as data:
                annotation_timeline_db = Timeline.objects.create(
                    video=video,
                    name=parameters["timeline"],
                    type=Timeline.TYPE_ANNOTATION,
                )

                category_db, _ = AnnotationCategory.objects.get_or_create(
                    name="Intensification", video=video, owner=user
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
                    "data": {"annotations": movie_pattern_intensify[1]["intensify"].id},
                }
