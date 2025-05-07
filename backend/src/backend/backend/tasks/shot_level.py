import logging
from typing import Dict

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

from ..utils.analyser_client import TaskAnalyserClient

from data import DataManager, Shot
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction
from django.conf import settings


logger = logging.getLogger(__name__)


@PluginManager.export_parser("shot_level")
class ShotLevelParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Shot Level"},
            "fps": {"parser": float, "default": 2.0},
            "shot_timeline_id": {},
        }


@PluginManager.export_plugin("shot_level")
class ShotLevel(Task):
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
            "shot_level",
            parameters={"fps": parameters.get("fps")},
            inputs={"video": video_id},
            outputs=["probs"],
            downloads=["probs"],
        )
        if result is None:
            raise Exception

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

        result_timelines = {}
        result_data = {}

        if shots_id:
            annotations_result = self.run_analyser(
                client,
                "shot_annotator",
                inputs={"probs": result[0]["probs"], "shots": shots_id},
                downloads=["annotations"],
            )
            if annotations_result is None:
                raise Exception

            """
            Create a timeline labeled by most probable class (per shot)
            """
            logger.info("Create annotation timeline")
            annotation_timeline = Timeline.objects.create(
                video=video,
                name=parameters.get("timeline"),
                type=Timeline.TYPE_ANNOTATION,
            )

            result_timelines["annotation"] = annotation_timeline.id.hex

            category_db, _ = AnnotationCategory.objects.get_or_create(
                name="Shot Level", video=video, owner=user
            )

            color_mapping = {
                "aerial": "#EDF2D1",
                "eye": "#DDE6A6",
                "shoulder": "#CEDA7D",
                "hip": "#BDCD52",
                "knee": "#AEC229",
                "ground": "#9EB600",
            }

            with annotations_result[1]["annotations"] as annotations:
                for annotation in annotations.annotations:
                    # create TimelineSegment
                    timeline_segment_db = TimelineSegment.objects.create(
                        timeline=annotation_timeline,
                        start=annotation.start,
                        end=annotation.end,
                    )

                    for label in annotation.labels:
                        # add annotion to TimelineSegment
                        annotation_db, _ = Annotation.objects.get_or_create(
                            name=label.title(),
                            video=video,
                            category=category_db,
                            owner=user,
                            color=color_mapping.get(label, "#EEEEEE"),
                        )

                        TimelineSegmentAnnotation.objects.create(
                            annotation=annotation_db,
                            timeline_segment=timeline_segment_db,
                        )
                result_data["annotations"] = annotations.id

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with result[1]["probs"] as data:
                data.extract_all(manager)
                for index, sub_data in zip(data.index, data.data):
                    plugin_run_result_db = PluginRunResult.objects.create(
                        plugin_run=plugin_run,
                        data_id=sub_data,
                        name="shot_level",
                        type=PluginRunResult.TYPE_SCALAR,
                    )
                    timeline_db = Timeline.objects.create(
                        video=video,
                        name=index.title(),
                        type=Timeline.TYPE_PLUGIN_RESULT,
                        plugin_run_result=plugin_run_result_db,
                        visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
                        parent=annotation_timeline,
                    )

                    result_timelines[index.title()] = timeline_db.id.hex

                result_data["probs"] = data.id

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [plugin_run_result_db.id.hex],
                    "timelines": result_timelines,
                    "data": result_data,
                }
