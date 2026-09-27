import io
import json
import logging
from typing import Dict, List

import imageio
import PIL.Image

from backend.models import (
    Annotation,
    AnnotationCategory,
    PluginRun,
    Timeline,
    TimelineSegment,
    TimelineSegmentAnnotation,
    TibavaUser,
    Video,
)
from backend.plugin_manager import PluginManager
from backend.utils import image_normalize, image_resize, media_path_to_video
from backend.utils.llm_client import (
    GeolocationLLMClient,
    MockGeolocationLLMClient,
    build_geolocation_prompt,
)
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

MAX_FRAMES_PER_SHOT = 4
MAX_FRAME_DIM = 1024


@PluginManager.export_parser("geolocation")
class GeolocationParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Geolocation"},
            "shot_timeline_id": {"default": None},
            "fps": {"parser": float, "default": 2},
            "confidence_threshold": {"parser": float, "default": 0.3},
            "year": {"parser": str, "default": None},
            "prompt": {"parser": str, "default": None},
        }


def _sample_timestamps(start: float, end: float, fps: float, max_frames: int) -> List[float]:
    if fps <= 0:
        fps = 1.0
    step = 1.0 / fps

    timestamps = []
    t = start
    while t < end and len(timestamps) < max_frames:
        timestamps.append(t)
        t += step

    if not timestamps:
        timestamps = [start]

    return timestamps


def _extract_shot_frames(video_path: str, shots_with_timestamps) -> Dict[str, List]:
    # Single sequential pass over the video collecting every sampled frame,
    # instead of seeking per-shot (slow/imprecise with ffmpeg-backed readers).
    targets = sorted(
        (
            (timestamp, shot_id)
            for shot_id, timestamps in shots_with_timestamps
            for timestamp in timestamps
        ),
        key=lambda x: x[0],
    )

    frames_by_shot: Dict[str, List] = {}
    if not targets:
        return frames_by_shot

    reader = imageio.get_reader(video_path)
    try:
        fps = reader.get_meta_data().get("fps") or 1.0
        target_idx = 0
        n_targets = len(targets)

        for frame_idx, frame in enumerate(reader):
            if target_idx >= n_targets:
                break
            frame_time = frame_idx / fps
            while target_idx < n_targets and frame_time >= targets[target_idx][0]:
                _, shot_id = targets[target_idx]
                frames_by_shot.setdefault(shot_id, []).append(frame)
                target_idx += 1
    finally:
        reader.close()

    return frames_by_shot


def _encode_frame_jpeg(frame, max_dim: int = MAX_FRAME_DIM) -> bytes:
    frame = image_normalize(frame)
    frame = image_resize(frame, max_dim=max_dim)
    buf = io.BytesIO()
    PIL.Image.fromarray(frame).convert("RGB").save(buf, format="JPEG")
    return buf.getvalue()


@PluginManager.export_plugin("geolocation")
class Geolocation(Task):
    def __init__(self):
        self.config = {
            "max_frames_per_shot": MAX_FRAMES_PER_SHOT,
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
        shot_timeline_id = parameters.get("shot_timeline_id")
        if not shot_timeline_id:
            raise ValueError("Geolocation requires a shot_timeline_id")

        if settings.DEBUG:
            client = MockGeolocationLLMClient()
        else:
            api_url = settings.GEOLOCATION_LLM_API_URL
            api_key = settings.GEOLOCATION_LLM_API_KEY
            model = settings.GEOLOCATION_LLM_API_MODEL
            if not api_url or not api_key or not model:
                raise ValueError(
                    "Geolocation LLM is not configured: set GEOLOCATION_LLM_API_URL, "
                    "GEOLOCATION_LLM_API_KEY, and GEOLOCATION_LLM_API_MODEL"
                )
            client = GeolocationLLMClient(
                api_url=api_url,
                api_key=api_key,
                model=model,
                timeout=settings.GEOLOCATION_LLM_TIMEOUT_SECONDS,
            )

        if plugin_run is not None:
            plugin_run.status = PluginRun.STATUS_RUNNING
            plugin_run.save()

        shot_timeline_db = Timeline.objects.get(id=shot_timeline_id)
        shot_segments = list(TimelineSegment.objects.filter(timeline=shot_timeline_db))
        if not shot_segments:
            raise ValueError("Selected shot timeline has no segments")

        video_path = media_path_to_video(video.file.hex, video.ext)
        fps = parameters.get("fps")
        confidence_threshold = parameters.get("confidence_threshold")

        shots_with_timestamps = [
            (shot.id, _sample_timestamps(shot.start, shot.end, fps, MAX_FRAMES_PER_SHOT))
            for shot in shot_segments
        ]
        frames_by_shot = _extract_shot_frames(video_path, shots_with_timestamps)

        prompt = build_geolocation_prompt(parameters.get("year"), parameters.get("prompt"))

        results_by_shot = {}
        n_shots = len(shot_segments)
        for i, shot in enumerate(shot_segments):
            frames = frames_by_shot.get(shot.id, [])
            if not frames:
                logger.warning("No frames extracted for shot %s, skipping", shot.id)
                results_by_shot[shot.id] = []
            else:
                encoded_frames = [_encode_frame_jpeg(frame) for frame in frames]
                candidates = client.locate(
                    encoded_frames, prompt, request_label=f"shot={shot.id}"
                )
                logger.info(
                    "Geolocation parsed candidates shot=%s (threshold=%s): %s",
                    shot.id,
                    confidence_threshold,
                    [(c["label"], c["confidence"]) for c in candidates],
                )
                results_by_shot[shot.id] = [
                    c for c in candidates if c["confidence"] >= confidence_threshold
                ]

            if plugin_run is not None:
                plugin_run.progress = (i + 1) / n_shots
                plugin_run.save()

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            category_db, _ = AnnotationCategory.objects.get_or_create(
                name="Geolocation", video=video, owner=user
            )

            # Replace a previous run's results for this video/category instead of
            # stacking a second timeline next to it.
            Timeline.objects.filter(
                video=video,
                timelinesegment__annotations__category=category_db,
            ).distinct().delete()
            Annotation.objects.filter(video=video, category=category_db).delete()

            annotation_timeline_db = Timeline.objects.create(
                video=video,
                name=parameters.get("timeline"),
                type=Timeline.TYPE_ANNOTATION,
            )

            for shot in shot_segments:
                timeline_segment_db = TimelineSegment.objects.create(
                    timeline=annotation_timeline_db,
                    start=shot.start,
                    end=shot.end,
                )

                for candidate in results_by_shot.get(shot.id, []):
                    annotation_db = Annotation.objects.create(
                        name=json.dumps(candidate),
                        video=video,
                        category=category_db,
                        owner=user,
                    )

                    TimelineSegmentAnnotation.objects.create(
                        annotation=annotation_db,
                        timeline_segment=timeline_segment_db,
                    )

            return {
                "plugin_run": plugin_run.id.hex,
                "plugin_run_results": [],
                "timelines": {"annotations": annotation_timeline_db.id.hex},
                "data": {},
            }
