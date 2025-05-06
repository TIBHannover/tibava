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
    "p_angry": "Angry",
    "p_disgust": "Disgust",
    "p_fear": "Fear",
    "p_happy": "Happy",
    "p_sad": "Sad",
    "p_surprise": "Surprise",
    "p_neutral": "Neutral",
}


@PluginManager.export_parser("deepface_emotion")
class DeepfaceEmotionParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Face Emotion"},
            "shot_timeline_id": {"default": None},
            "fps": {"parser": float, "default": 2},
            "min_facesize": {"parser": int, "default": 48},
        }


@PluginManager.export_plugin("deepface_emotion")
class DeepfaceEmotion(Task):
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

        # start plugins
        result = self.run_analyser(
            client,
            "insightface_video_detector_torch",
            parameters={
                "fps": parameters.get("fps"),
                "min_facesize": parameters.get("min_facesize"),
            },
            inputs={"video": video_id},
            outputs=["images", "faces"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.25
            plugin_run.save()

        if result is None:
            raise Exception

        emotion_result = self.run_analyser(
            client,
            "deepface_emotion",
            inputs={**result[0]},
            outputs=["probs"],
            downloads=["probs"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.5
            plugin_run.save()

        if emotion_result is None:
            raise Exception

        aggregate_result = self.run_analyser(
            client,
            "aggregate_list_scalar_per_time",
            inputs={"scalars": emotion_result[0]["probs"]},
            downloads=["aggregated_scalars"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.75
            plugin_run.save()

        if aggregate_result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with aggregate_result[1]["aggregated_scalars"] as data:

                timeline_dict = {}
                # Annotate shots
                annotation_timeline_db = None
                if shots_id:

                    annotater_result = self.run_analyser(
                        client,
                        "shot_annotator",
                        inputs={"shots": shots_id, "probs": data.id},
                        downloads=["annotations"],
                    )

                    if annotater_result is None:
                        raise Exception
                    with annotater_result[1]["annotations"] as annotations_data:

                        annotation_timeline_db = Timeline.objects.create(
                            video=video,
                            name=parameters.get("timeline"),
                            type=Timeline.TYPE_ANNOTATION,
                        )

                        timeline_dict.update({"annotations": annotation_timeline_db})

                        category_db, _ = AnnotationCategory.objects.get_or_create(
                            name="Emotion", video=video, owner=user
                        )

                        for annotation in annotations_data.annotations:
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

                data.extract_all(manager)
                data_list = {}

                plugin_run_results = []

                for index, sub_data in zip(data.index, data.data):

                    plugin_run_result_db = PluginRunResult.objects.create(
                        plugin_run=plugin_run,
                        data_id=sub_data,
                        name="face_emotion",
                        type=PluginRunResult.TYPE_SCALAR,
                    )
                    plugin_run_results.append(plugin_run_result_db.id.hex)

                    timeline_db = Timeline.objects.create(
                        video=video,
                        name=LABEL_LUT.get(index, index),
                        type=Timeline.TYPE_PLUGIN_RESULT,
                        plugin_run_result=plugin_run_result_db,
                        visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
                        parent=annotation_timeline_db,
                    )
                    timeline_dict.update({index: timeline_db.id.hex})
                    data_list.update({index: sub_data})

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": plugin_run_results,
                    "timelines": {
                        **timeline_dict,
                    },
                    "data": {
                        "annotations": aggregate_result[1]["aggregated_scalars"].id,
                        **data_list,
                    },
                }
