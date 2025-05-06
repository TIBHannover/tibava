from typing import Dict, List
import logging

from ..utils.analyser_client import TaskAnalyserClient

from backend.models import PluginRun, PluginRunResult, Video, Timeline
from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video
from backend.utils.parser import Parser
from backend.utils.task import Task
from data import Shot, DataManager
from backend.models import (
    AnnotationCategory,
    TimelineSegment,
    Annotation,
    TimelineSegmentAnnotation,
    TibavaUser,
)
from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("blip_vqa")
class BLIPVQAParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "blip_vqa"},
            "shot_timeline_id": {"required": True},
            "query_term": {"parser": str, "required": True},
        }


@PluginManager.export_plugin("blip_vqa")
class BLIPVQA(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": settings.GRPC_HOST,
            "analyser_port": settings.GRPC_PORT,
        }

    def __call__(
        self,
        parameters: Dict,
        user: TibavaUser = None,
        video: Video = None,
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
            "timeline_video_sampler",
            parameters={
                "middle_frame": True,
                "start_frame": False,
                "end_frame": False,
            },
            inputs={"input": video_id, "shots": shots_id},
            outputs=["output"],
        )
        if result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "blip_image_embedding",
            parameters={},
            inputs={"input": result[0]["output"]},
            outputs=["embeddings"],
        )

        if result is None:
            raise Exception

        if plugin_run is not None:
            plugin_run.progress = 0.5
            plugin_run.save()

        if result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "blip_vqa",
            parameters={"query_term": parameters.get("query_term")},
            inputs={**result[0], "shots": shots_id},
            downloads=["annotations"],
        )
        if result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with result[1]["annotations"] as data:

                # print("A", flush=True)
                """
                Create a timeline labeled
                """
                # print(f"[{PLUGIN_NAME}] Create annotation timeline", flush=True)
                annotation_timeline_db = Timeline.objects.create(
                    video=video,
                    name=parameters.get("timeline"),
                    type=Timeline.TYPE_ANNOTATION,
                )

                category_db, _ = AnnotationCategory.objects.get_or_create(
                    name="Blib", video=video, owner=user
                )

                # print("B", flush=True)
                for annotation in data.annotations:
                    timeline_segment_db = TimelineSegment.objects.create(
                        timeline=annotation_timeline_db,
                        start=annotation.start,
                        end=annotation.end,
                    )
                    # print(f"C {annotation.start} {annotation.end}", flush=True)
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
                            # color=color,
                        )
                        # print(f"D {str(label)}", flush=True)

                        TimelineSegmentAnnotation.objects.create(
                            annotation=annotation_db,
                            timeline_segment=timeline_segment_db,
                        )

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [],
                    "timelines": {"annotations": annotation_timeline_db.id.hex},
                    "data": {"annotations": result[1]["annotations"].id},
                }
