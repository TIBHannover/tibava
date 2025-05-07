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


@PluginManager.export_parser("shot_scale_and_movement")
class ShotScaleAndMovementParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline_scale": {"parser": str, "default": "Shot Scale"},
            "timeline_movement": {"parser": str, "default": "Shot Movement"},
            "fps": {"parser": float, "default": 25.0},
            "shot_timeline_id": {},
        }


@PluginManager.export_plugin("shot_scale_and_movement")
class ShotScaleAndMovement(Task):
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
            "shot_scale_and_movement",
            parameters={"fps": parameters.get("fps")},
            inputs={"video": video_id},
            outputs=["scale_probs", "movement_probs"],
            downloads=["scale_probs", "movement_probs"],
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

        scale_cfg = {
            "shots_id": shots_id,
            "client": client,
            "video": video,
            "user": user,
            "manager": manager,
            "plugin_run": plugin_run,
            "dry_run": dry_run,
            "probs": result[0]["scale_probs"],
            "probs_downloaded": result[1]["scale_probs"],
            "timeline_name": parameters.get("timeline_scale"),
            "cat_name": "Shot Scale",
            "result_name": "shot_scale",
            "label_LUT": {
                "LS": "Long",
                "FS": "Full",
                "MS": "Medium",
                "CS": "Close-Up",
                "ECS": "Extreme Close-Up",
            },
            "color_mapping": {
                "LS": "#ECF0CC",
                "FS": "#D8E299",
                "MS": "#C5D366",
                "CS": "#B1C533",
                "ECS": "#9EB600",
            },
        }
        scale_result_data, scale_timelines, scale_db = self.create_timeline(scale_cfg)
        movement_cfg = {
            "shots_id": shots_id,
            "client": client,
            "video": video,
            "user": user,
            "manager": manager,
            "plugin_run": plugin_run,
            "dry_run": dry_run,
            "probs": result[0]["movement_probs"],
            "probs_downloaded": result[1]["movement_probs"],
            "timeline_name": parameters.get("timeline_movement"),
            "cat_name": "Shot Movement",
            "result_name": "shot_movement",
            "label_LUT": {
                "Static": "Static",
                "Motion": "Motion",
                "Push": "Push",
                "Pull": "Pull",
            },
            "color_mapping": {
                "Static": "#4AA5C2",
                "Motion": "#AFBD79",
                "Push": "#AF95AF",
                "Pull": "#D39581",
            },
        }
        movement_result_data, movement_timelines, movement_db = self.create_timeline(
            movement_cfg
        )

        return {
            "plugin_run": plugin_run.id.hex,
            "plugin_run_results": [scale_db.id.hex, movement_db.id.hex],
            "timelines": {
                **scale_timelines,
                **movement_timelines,
            },
            "data": {
                **scale_result_data,
                **movement_result_data,
            },
        }

    def create_timeline(self, cfg):
        result_timelines = {}
        result_data = {}

        if cfg["shots_id"]:
            annotations_result = self.run_analyser(
                cfg["client"],
                "shot_annotator",
                inputs={"probs": cfg["probs"], "shots": cfg["shots_id"]},
                downloads=["annotations"],
            )
            if annotations_result is None:
                raise Exception

            """
            Create a timeline labeled by most probable class (per shot)
            """
            logger.info("Create annotation timeline")
            annotation_timeline = Timeline.objects.create(
                video=cfg["video"],
                name=cfg["timeline_name"],
                type=Timeline.TYPE_ANNOTATION,
            )

            result_timelines[cfg["timeline_name"]] = annotation_timeline.id.hex

            category_db, _ = AnnotationCategory.objects.get_or_create(
                name=cfg["cat_name"], video=cfg["video"], owner=cfg["user"]
            )

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
                            name=cfg["label_LUT"].get(label, f"'{label}' not in LUT"),
                            video=cfg["video"],
                            category=category_db,
                            owner=cfg["user"],
                            color=cfg["color_mapping"].get(label, "#EEEEEE"),
                        )

                        TimelineSegmentAnnotation.objects.create(
                            annotation=annotation_db,
                            timeline_segment=timeline_segment_db,
                        )
                result_data[f"{cfg['result_name']}_annotations"] = annotations.id

        if cfg["dry_run"] or cfg["plugin_run"] is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with cfg["probs_downloaded"] as data:
                data.extract_all(cfg["manager"])
                for index, sub_data in zip(data.index, data.data):
                    plugin_run_result_db = PluginRunResult.objects.create(
                        plugin_run=cfg["plugin_run"],
                        data_id=sub_data,
                        name=cfg["result_name"],
                        type=PluginRunResult.TYPE_SCALAR,
                    )
                    timeline_db = Timeline.objects.create(
                        video=cfg["video"],
                        name=cfg["label_LUT"].get(index, f"'{index}' not in LUT"),
                        type=Timeline.TYPE_PLUGIN_RESULT,
                        plugin_run_result=plugin_run_result_db,
                        visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
                        parent=annotation_timeline,
                    )

                    result_timelines[index.title()] = timeline_db.id.hex

                result_data[f"{cfg['result_name']}_probs"] = data.id

        return result_data, result_timelines, plugin_run_result_db
