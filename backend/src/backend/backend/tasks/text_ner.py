from typing import Dict
import logging

from ..utils.analyser_client import TaskAnalyserClient

from backend.models import PluginRun, Video, Timeline
from backend.plugin_manager import PluginManager

from backend.utils.parser import Parser
from backend.utils.task import Task

from data import DataManager  # type: ignore
from backend.models import (
    Annotation,
    PluginRun,
    TimelineSegmentAnnotation,
    Video,
    TibavaUser,
    Timeline,
    TimelineSegment,
)
from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("text_ner")
class NamedEntityRecognitionParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Named Entities"},
            # TODO maybe add language parameter if multiple languages are supported
        }


@PluginManager.export_plugin("text_ner")
class NamedEntityRecognition(Task):
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
        audio_result = self.run_analyser(
            client,
            "video_to_audio",
            inputs={"video": video_id},
            outputs=["audio"],
        )
        if audio_result is None:
            raise Exception

        if plugin_run is not None:
            plugin_run.progress = 0.3
            plugin_run.save()

        segmentation_result = self.run_analyser(
            client,
            "whisper_x",
            parameters={"language_code": None},
            inputs={**audio_result[0]},
            outputs=["annotations"],
        )
        if segmentation_result is None:
            raise Exception

        if plugin_run is not None:
            plugin_run.progress = 0.7
            plugin_run.save()

        result = self.run_analyser(
            client,
            "text_ner",
            inputs={
                "annotations": segmentation_result[0]["annotations"],
            },
            downloads=["annotations"],
        )

        logging.info(f"{result=}")
        if result is None:
            raise Exception

        def create_timeline(
            data,
            timeline_name: str,
            annotation_key: str,
            color_mapping: Dict[str, str],
            color_key: str,
        ):
            data.load()

            result_timeline = {}
            timeline = Timeline.objects.create(
                video=video,
                name=timeline_name,
                type=Timeline.TYPE_ANNOTATION,
            )
            result_timeline[f"{timeline_name}_{data.name}"] = timeline.id.hex
            for annotation in data.annotations:
                timeline_segment_db = TimelineSegment.objects.create(
                    timeline=timeline,
                    start=annotation.start,
                    end=annotation.end,
                )
                for annotation_object in annotation.labels:
                    for label_object in annotation_object["tags"]:
                        label = label_object[annotation_key]
                        if len(label) > settings.ANNOTATION_MAX_LENGTH:
                            label = (
                                label[: max(0, settings.ANNOTATION_MAX_LENGTH - 4)]
                                + " ..."
                            )
                        annotation_db, _ = Annotation.objects.get_or_create(
                            name=label,
                            video=video,
                            owner=user,
                            color=color_mapping.get(label_object[color_key], "#EEEEEE"),
                        )

                        TimelineSegmentAnnotation.objects.create(
                            annotation=annotation_db,
                            timeline_segment=timeline_segment_db,
                        )
            return result_timeline

        with transaction.atomic():
            result_timelines = {}
            with result[1]["annotations"] as data:
                color_mapping = {
                    "EPER": "#FBFBD3",
                    "LPER": "#D1ACB3",
                    "LOC": "#5CB2DE",
                    "ORG": "#FAC0AB",
                    "EVENT": "#F9C6FA",
                    "MISC": "#C8F9FF",
                }

                result_timelines.update(
                    create_timeline(
                        data,
                        parameters["timeline"],
                        "wd_label",
                        color_mapping,
                        color_key="type",
                    )
                )

            return {
                "plugin_run": plugin_run.id.hex,
                "plugin_run_results": [],
                "timelines": result_timelines,
                "data": {
                    "annotations": result[1]["annotations"].id,
                },
            }
