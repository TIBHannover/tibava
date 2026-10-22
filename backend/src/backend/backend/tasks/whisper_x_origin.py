import logging
from typing import Dict

from django.conf import settings
from django.db import transaction
from tibava_data import DataManager  # type: ignore

from backend.models import (
    Annotation,
    AnnotationCategory,
    PluginRun,
    TibavaUser,
    Timeline,
    TimelineSegment,
    TimelineSegmentAnnotation,
    Video,
)
from backend.plugin_manager import PluginManager
from backend.utils.parser import Parser
from backend.utils.task import Task

from ..utils.analyser_client import TaskAnalyserClient


@PluginManager.export_parser("whisper_x_origin")
class WhisperXOriginParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "WhisperXOrigin Transcript"},
            "language_code": {"parser": str, "default": None},
            "threshold": {"parser": float, "default": 0.6},
            "Fb": {"parser": float, "default": 0.8},
            "Fa": {"parser": float, "default": 0.07},
        }

    def __call__(self, parameters: Dict = None, **kwargs) -> Dict:
        parameters = super().__call__(parameters, **kwargs)
        if parameters["language_code"] == "none":
            parameters["language_code"] = None
        return parameters


@PluginManager.export_plugin("whisper_x_origin")
class WhisperXOrigin(Task):
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
        result = self.run_analyser(
            client,
            "video_to_audio",
            parameters={"sample_rate": 16000},
            inputs={"video": video_id},
            outputs=["audio"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.5
            plugin_run.save()

        if result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "whisper_x_origin",
            parameters={
                "language_code": parameters.get("language_code"),
                "threshold": parameters.get("threshold"),
                "Fb": parameters.get("Fb"),
                "Fa": parameters.get("Fa"),
            },
            inputs={**result[0]},
            downloads=["transcript", "speaker"],
        )
        if result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with (
                result[1]["transcript"] as transcript_data,
                result[1]["speaker"] as speaker_data,
            ):
                """
                Create a timeline labeled
                """

                parent_timeline = Timeline.objects.create(
                    video=video,
                    name=parameters["timeline"],
                    type=Timeline.TYPE_ANNOTATION,
                )

                category_db, _ = AnnotationCategory.objects.get_or_create(
                    name="Transcript", video=video, owner=user
                )
                result_timelines = {}

                timeline = Timeline.objects.create(
                    video=video,
                    name=transcript_data.name,
                    type=Timeline.TYPE_TRANSCRIPT,
                    parent=parent_timeline,
                )
                result_timelines[transcript_data.name] = timeline.id.hex
                color_list = ["#DDDDDD", "#EEEEEE"]  # white/gray
                for anno_id, annotation in enumerate(transcript_data.annotations):
                    timeline_segment_db = TimelineSegment.objects.create(
                        timeline=timeline,
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
                            color=color_list[anno_id % 2],  # white/gray
                        )

                        TimelineSegmentAnnotation.objects.create(
                            annotation=annotation_db,
                            timeline_segment=timeline_segment_db,
                        )

                timeline = Timeline.objects.create(
                    video=video,
                    name=speaker_data.name,
                    type=Timeline.TYPE_ANNOTATION,
                    parent=parent_timeline,
                )
                result_timelines[speaker_data.name] = timeline.id.hex
                for annotation in speaker_data.annotations:
                    timeline_segment_db = TimelineSegment.objects.create(
                        timeline=timeline,
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
                            owner=user,
                        )

                        TimelineSegmentAnnotation.objects.create(
                            annotation=annotation_db,
                            timeline_segment=timeline_segment_db,
                        )

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [],
                    "timelines": result_timelines,
                    # "data": {"annotations": result[1]["annotations"].id},  # TODO
                }
