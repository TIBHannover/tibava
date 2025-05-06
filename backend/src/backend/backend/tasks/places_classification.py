from typing import Dict, List
import logging
from ..utils.analyser_client import TaskAnalyserClient

from data import Shot, ShotsData
from data import DataManager

from backend.models import (
    Annotation,
    AnnotationCategory,
    PluginRun,
    PluginRunResult,
    TimelineSegmentAnnotation,
    Video,
    TibavaUser,
    Timeline,
    TimelineSegment,
)
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from celery import shared_task
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction
from django.conf import settings


CATEGORY_LUT = {
    "probs_places365": "Places365",
    "probs_places16": "Places16",
    "probs_places3": "Places3",
}


@PluginManager.export_parser("places_classification")
class PlacesClassifierParser(Parser):
    def __init__(self):

        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Places"},
            "shot_timeline_id": {"default": None},
            "fps": {"parser": float, "default": 2},
        }


@PluginManager.export_plugin("places_classification")
class PlacesClassifier(Task):
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
            "places_classifier",
            parameters={
                "fps": parameters.get("fps"),
            },
            inputs={"video": video_id},
            outputs=["probs_places365", "probs_places16", "probs_places3"],
            downloads=["probs_places3"],
        )

        if result is None:
            raise Exception

        result_timelines = {}
        result_data = {}

        if plugin_run is not None:
            plugin_run.progress = 0.5
            plugin_run.save()

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            result_annotations = {}
            if shots_id:
                for key, data_id in result[0].items():
                    result_annotations[key] = None

                    annotation_result = self.run_analyser(
                        client,
                        "shot_annotator",
                        parameters={
                            "fps": parameters.get("fps"),
                        },
                        inputs={"shots": shots_id, "probs": data_id},
                        downloads=["annotations"],
                    )

                    result_annotations[key] = annotation_result[1]["annotations"]
            annotation_timeline = Timeline.objects.create(
                video=video,
                name=parameters.get("timeline"),
                type=Timeline.TYPE_ANNOTATION,
            )

            result_timelines["annotation"] = annotation_timeline.id.hex

            segments = {}
            for shot in shots.shots:
                timeline_segment_db = TimelineSegment.objects.create(
                    timeline=annotation_timeline,
                    start=shot.start,
                    end=shot.end,
                )
                segments[shot.start] = timeline_segment_db

            category_lut = {
                "probs_places365": "Places365",
                "probs_places16": "Places16",
                "probs_places3": "Places3",
            }
            for key in result_annotations:
                category_db, _ = AnnotationCategory.objects.get_or_create(
                    name=category_lut[key], video=video, owner=user
                )
                with result_annotations[key] as annotations:
                    for annotation in annotations.annotations:
                        for label in annotation.labels:
                            # add annotion to TimelineSegment
                            annotation_db, _ = Annotation.objects.get_or_create(
                                name=label,
                                video=video,
                                category=category_db,
                                owner=user,
                            )

                            timeline_db = TimelineSegmentAnnotation.objects.create(
                                annotation=annotation_db,
                                timeline_segment=segments[annotation.start],
                            )

                    result_data[key] = result_annotations[key].id

            """
            TODO: Create hierarchical timeline(s) with probability of each place category (per hierarchy level) as scalar data
            """
            print(
                f"[PlacesClassifier] Create scalar color (SC) timeline with probabilities for each class",
                flush=True,
            )
            # if parameters.get("show_probs"):
            print(result, flush=True)
            with result[1]["probs_places3"] as probs:
                probs.extract_all(manager)

                for index, sub_data in zip(probs.index, probs.data):

                    plugin_run_result_db = PluginRunResult.objects.create(
                        plugin_run=plugin_run,
                        data_id=sub_data,
                        name="places_classification",
                        type=PluginRunResult.TYPE_SCALAR,
                    )
                    timeline_db = Timeline.objects.create(
                        video=video,
                        name=index,
                        type=Timeline.TYPE_PLUGIN_RESULT,
                        plugin_run_result=plugin_run_result_db,
                        visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
                        parent=annotation_timeline,
                    )

                    result_timelines[index] = timeline_db.id.hex

                result_data["probs_places3"] = probs.id

            return {
                "plugin_run": plugin_run.id.hex,
                "plugin_run_results": [plugin_run_result_db.id.hex],
                "timelines": result_timelines,
                "data": result_data,
            }
