from typing import Dict
import logging

from ..utils.analyser_client import TaskAnalyserClient

from backend.models import PluginRun, Video, Timeline
from backend.plugin_manager import PluginManager

from backend.utils.parser import Parser
from backend.utils.task import Task
from backend.utils.color import color_map

from data import DataManager  # type: ignore
from backend.models import (
    Annotation,
    AnnotationCategory,
    PluginRun,
    TimelineSegmentAnnotation,
    Video,
    TibavaUser,
    Timeline,
    TimelineSegment,
)
from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("audio_gender")
class AudioGenderParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Audio Gender Classification"},
        }


@PluginManager.export_plugin("audio_gender")
class AudioGender(Task):
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

        if plugin_run is not None:
            plugin_run.progress = 0.3
            plugin_run.save()

        if audio_result is None:
            raise Exception

        whisper_result = self.run_analyser(
            client,
            "whisper_x",
            parameters={"language_code": None},
            inputs={**audio_result[0]},
            outputs=["annotations"],
        )
        if whisper_result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "audio_gender",
            inputs={
                "audio": audio_result[0]["audio"],
                "annotations": whisper_result[0]["annotations"],
            },
            downloads=["annotations"],
        )
        if result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        def create_timelines(
            ann_data,
            timelines_name: str,
            annotation_key: str,
            prob_key: str,
            genders: Dict[str, int],
            color_mapping: Dict[str, str],
        ):
            ann_data.load()

            category_db, _ = AnnotationCategory.objects.get_or_create(
                name=timelines_name, video=video, owner=user
            )

            parent_timeline = Timeline.objects.create(
                video=video,
                name=timelines_name,
                type=Timeline.TYPE_ANNOTATION,
            )
            result_timelines = {"annotation": parent_timeline.id.hex}

            for annotation in ann_data.annotations:
                timeline_segment_db = TimelineSegment.objects.create(
                    timeline=parent_timeline,
                    start=annotation.start,
                    end=annotation.end,
                )

                label = str(annotation.labels[0][annotation_key])

                annotation_db, _ = Annotation.objects.get_or_create(
                    name=label.title(),
                    video=video,
                    owner=user,
                    category=category_db,
                    color=color_mapping[label],
                )

                TimelineSegmentAnnotation.objects.create(
                    annotation=annotation_db,
                    timeline_segment=timeline_segment_db,
                )

            for gender, idx in genders.items():
                timeline = Timeline.objects.create(
                    video=video,
                    name=gender.title(),
                    type=Timeline.TYPE_ANNOTATION,
                    visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
                    parent=parent_timeline,
                )
                result_timelines[gender] = timeline.id.hex

                for annotation in ann_data.annotations:
                    timeline_segment_db = TimelineSegment.objects.create(
                        timeline=timeline,
                        start=annotation.start,
                        end=annotation.end,
                    )

                    prob = annotation.labels[0][prob_key][idx]

                    annotation_db, _ = Annotation.objects.get_or_create(
                        name=f"{round(prob * 100, 1)}%",
                        video=video,
                        owner=user,
                        color=color_map(prob),
                    )

                    TimelineSegmentAnnotation.objects.create(
                        annotation=annotation_db,
                        timeline_segment=timeline_segment_db,
                    )

            return result_timelines

        with transaction.atomic():
            with result[1]["annotations"] as ann_data:
                genders = {"female": 0, "male": 1}

                color_mapping = {
                    "female": "#FFB7B8",  # light red
                    "male": "#B6DCFF",  # light blue
                }

                result_timelines = create_timelines(
                    ann_data,
                    parameters["timeline"],
                    "gender_pred",
                    "gender_probs",
                    genders,
                    color_mapping,
                )

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [],
                    "timelines": result_timelines,
                    "data": {
                        "annotations": result[1]["annotations"].id,
                    },
                }
