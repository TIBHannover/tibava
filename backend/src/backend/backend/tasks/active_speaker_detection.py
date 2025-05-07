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

from ..utils.analyser_client import TaskAnalyserClient
from data import Shot, ShotsData, DataManager
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("active_speaker_detection")
class ActiveSpeakerDetectionParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Active Speaker Detection"},
            "shot_timeline_id": {"default": None},
            "fps": {"parser": float, "default": 2.0},
        }


@PluginManager.export_plugin("active_speaker_detection")
class ActiveSpeakerDetection(Task):
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

        audio_result = self.run_analyser(
            client,
            "video_to_audio",
            inputs={"video": video_id},
            outputs=["audio"],
        )
        if audio_result is None:
            raise Exception

        shots_id = None
        if parameters.get("shot_timeline_id"):
            shot_timeline_segments = TimelineSegment.objects.filter(
                timeline__id=parameters.get("shot_timeline_id")
            )
            shots = manager.create_data("ShotsData")
            with shots:
                for x in shot_timeline_segments:
                    shots.shots.append(Shot(start=x.start, end=x.end))
            shots_id = client.upload_data(shots)

        if plugin_run is not None:
            plugin_run.progress = 0.5
            plugin_run.save()

        facedetector_result = self.run_analyser(
            client,
            "insightface_video_detector_torch",
            parameters={
                "fps": parameters.get("fps"),
            },
            inputs={"video": video_id},
            outputs=["faces", "bboxes"],
        )
        if facedetector_result is None:
            raise Exception

        if plugin_run is not None:
            plugin_run.progress = 0.75
            plugin_run.save()

        facetracking_result = self.run_analyser(
            client,
            "face_tracking",
            inputs={
                "bboxes": facedetector_result[0]["bboxes"],
                "faces": facedetector_result[0]["faces"],
                "shots": shots_id,
            },
            outputs=["track_data"],
        )
        if facetracking_result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "active_speaker_detection",
            parameters={"fps": parameters.get("fps")},
            inputs={
                "video": video_id,
                "audio": audio_result[0]["audio"],
                "face_tracks": facetracking_result[0]["track_data"],
            },
            downloads=["speaker_tracks"],
        )

        if result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with result[1]["speaker_tracks"] as track_data:
                logging.info(f"{track_data=}")

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [],
                    "timelines": {},
                    "data": {"speaker_tracks": result[1]["speaker_tracks"].id},
                }
