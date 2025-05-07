from typing import Dict
import logging

from ..utils.analyser_client import TaskAnalyserClient

from backend.models import PluginRun, Video, Timeline
from backend.plugin_manager import PluginManager

from backend.utils.parser import Parser
from backend.utils.task import Task
from backend.utils.color import get_color_from_label

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


@PluginManager.export_parser("audio_classification")
class AudioClassificationParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Audio Classification"},
            "segment_type": {"parser": str},  # Speaker or Shot
        }


@PluginManager.export_plugin("audio_classification")
class AudioClassification(Task):
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

        if parameters.get("segment_type") == "Speaker":
            segmentation_result = self.run_analyser(
                client,
                "whisper_x",
                parameters={"language_code": None},
                inputs={**audio_result[0]},
                outputs=["annotations"],
            )
        elif parameters.get("segment_type") == "Shot":
            segmentation_result = self.run_analyser(
                client,
                "transnet_shotdetection",
                parameters={"fps": 2.0},  # default value
                inputs={"video": video_id},
                outputs=["shots"],
            )
            logging.info(segmentation_result)
            segmentation_result[0]["annotations"] = segmentation_result[0]["shots"]
        else:
            raise NotImplementedError(
                f"Unknown segment type: {parameters.get('segment_type')}"
            )
        if segmentation_result is None:
            raise Exception

        logging.info(f"{segmentation_result=}")

        result = self.run_analyser(
            client,
            "audio_classification",
            inputs={
                "audio": audio_result[0]["audio"],
                "annotations": segmentation_result[0]["annotations"],
            },
            parameters={"segment_type": parameters.get("segment_type")},
            downloads=["annotations"],
        )

        logging.info(f"{result=}")
        if result is None:
            raise Exception

        def create_timelines(
            data,
            timelines_name: str,
            annotation_key: str,
        ):
            data.extract_all(manager)

            parent_timeline = Timeline.objects.create(
                video=video,
                name=timelines_name,
                type=Timeline.TYPE_ANNOTATION,
            )

            result_timelines = {}
            for _, sub_data in data:
                with sub_data as sub_data:
                    timeline = Timeline.objects.create(
                        video=video,
                        name=sub_data.name,
                        type=Timeline.TYPE_ANNOTATION,
                        parent=parent_timeline,
                    )
                    result_timelines[f"{timelines_name}_{sub_data.name}"] = (
                        timeline.id.hex
                    )
                    for annotation in sub_data.annotations:
                        timeline_segment_db = TimelineSegment.objects.create(
                            timeline=timeline,
                            start=annotation.start,
                            end=annotation.end,
                        )
                        for label_object in annotation.labels:
                            label = str(label_object[annotation_key])
                            if len(label) > settings.ANNOTATION_MAX_LENGTH:
                                label = (
                                    label[: max(0, settings.ANNOTATION_MAX_LENGTH - 4)]
                                    + " ..."
                                )
                            annotation_db, _ = Annotation.objects.get_or_create(
                                name=label,
                                video=video,
                                owner=user,
                                color=get_color_from_label(label),
                            )

                            TimelineSegmentAnnotation.objects.create(
                                annotation=annotation_db,
                                timeline_segment=timeline_segment_db,
                            )
            return result_timelines

        with transaction.atomic():
            result_timelines = {}
            with result[1]["annotations"] as data:
                logging.info(data)
                result_timelines.update(
                    create_timelines(data, parameters["timeline"], "label_pred")
                )

            return {
                "plugin_run": plugin_run.id.hex,
                "plugin_run_results": [],
                "timelines": result_timelines,
                "data": {
                    "annotations": result[1]["annotations"].id,
                },
            }
