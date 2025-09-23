from typing import Dict, List
import imageio.v3 as iio

from data import DataManager
from backend.models import (
    PluginRun,
    PluginRunResult,
    Video,
    Timeline,
    TibavaUser,
    Annotation,
    AnnotationCategory,
    PluginRun,
    PluginRunResult,
    TimelineSegmentAnnotation,
    TimelineSegment,
)
from backend.plugin_manager import PluginManager

from ..utils.analyser_client import TaskAnalyserClient
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction

from django.conf import settings


@PluginManager.export_parser("nano_ocr_video")
class NanoOCRParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "OCR"},
            "fps": {"parser": float, "default": 1},
        }


@PluginManager.export_plugin("nano_ocr_video")
class NanoOCRTask(Task):
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

        # text detection on video
        video_text_detection_result = self.run_analyser(
            client,
            "nano_ocr_video",
            parameters={
                "fps": parameters.get("fps"),
            },
            inputs={"video": video_id},
            downloads=["annotations"],
        )

        if video_text_detection_result is None:
            raise Exception

        with transaction.atomic():
            with video_text_detection_result[1]["annotations"] as data:
                """
                Create a timeline labeled
                """
                annotation_timeline_db = Timeline.objects.create(
                    video=video,
                    name=parameters.get("timeline"),
                    type=Timeline.TYPE_ANNOTATION,
                )

                category_db, _ = AnnotationCategory.objects.get_or_create(
                    name="Transcript", video=video, owner=user
                )

                for annotation in data.annotations:
                    timeline_segment_db = TimelineSegment.objects.create(
                        timeline=annotation_timeline_db,
                        start=annotation.start,
                        end=annotation.end,
                    )
                    for label in annotation.labels:
                        annotation_db, _ = Annotation.objects.get_or_create(
                            name=str(label),
                            video=video,
                            category=category_db,
                            owner=user,
                            # color=color,
                        )

                        TimelineSegmentAnnotation.objects.create(
                            annotation=annotation_db,
                            timeline_segment=timeline_segment_db,
                        )

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [],
                    "timelines": {"annotations": annotation_timeline_db},
                    "data": {
                        "annotations": video_text_detection_result[1]["annotations"].id
                    },
                }

            # with video_text_detection_result[1]['bboxes'] as data:
            #     plugin_run_result_db = PluginRunResult.objects.create(
            #         plugin_run=plugin_run,
            #         data_id=data.id,
            #         name="ocr",
            #         type=PluginRunResult.TYPE_SCALAR,
            #     )

            #     return {
            #         "plugin_run": plugin_run.id.hex,
            #         "plugin_run_results": [plugin_run_result_db.id.hex],
            #         "timelines": {},
            #         "data": {"annotations": data.id}
            #     }
