from typing import Dict, List
import logging

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
from data import Shot, ShotsData, DataManager
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction
from django.conf import settings


LABEL_LUT = {
    "p_ECU": "Extreme Close-Up",
    "p_CU": "Close-Up",
    "p_MS": "Medium Shot",
    "p_FS": "Full Shot",
    "p_LS": "Long Shot",
}


@PluginManager.export_parser("insightface_facesize")
class InsightfaceFacesizeParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Face Size"},
            "shot_timeline_id": {"default": None},
            "fps": {"parser": float, "default": 2.0},
        }


@PluginManager.export_plugin("insightface_facesize")
class InsightfaceFacesize(Task):
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
        shot_type_results = self.run_analyser(
            client,
            "shot_type_classifier",
            inputs={"video": video_id},
            outputs=["probs"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.25
            plugin_run.save()

        if shot_type_results is None:
            raise Exception

        shot_size_annotation = self.run_analyser(
            client,
            "shot_annotator",
            inputs={"probs": shot_type_results[0]["probs"], "shots": shots_id},
            outputs=["annotations"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.5
            plugin_run.save()

        if shot_size_annotation is None:
            raise Exception

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

        facesize_result = self.run_analyser(
            client,
            "insightface_facesize",
            inputs={
                "shot_annotation": shot_size_annotation[0]["annotations"],
                "bboxes": facedetector_result[0]["bboxes"],
                "shots": shots_id,
            },
            outputs=["annotations"],
            downloads=["annotations"],
        )

        if facesize_result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with facesize_result[1]["annotations"] as annotations:

                annotation_timeline_db = Timeline.objects.create(
                    video=video,
                    name=parameters.get("timeline"),
                    type=Timeline.TYPE_ANNOTATION,
                )

                category_db, _ = AnnotationCategory.objects.get_or_create(
                    name="Face Size", video=video, owner=user
                )
                for annotation in annotations.annotations:
                    # create TimelineSegment
                    timeline_segment_db = TimelineSegment.objects.create(
                        timeline=annotation_timeline_db,
                        start=annotation.start,
                        end=annotation.end,
                    )

                    for label in annotation.labels:
                        # add annotion to TimelineSegment
                        annotation_db, _ = Annotation.objects.get_or_create(
                            name=LABEL_LUT.get(label, label),
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
                    "data": {"annotations": facesize_result[1]["annotations"].id},
                }
