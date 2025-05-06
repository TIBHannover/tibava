import logging
import os
from random import random
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from backend.utils.color import rgb_to_hex, random_rgb

from data import DataManager
from backend.utils import media_path_to_video
from .managers import TibavaUserManager


logger = logging.getLogger(__name__)


def random_color_string():
    return rgb_to_hex(random_rgb())


class TibavaUser(AbstractUser):
    allowance = models.IntegerField(default=10)
    max_video_size = models.BigIntegerField(default=500 * 1024 * 1024)  # 50 Mb
    objects = TibavaUserManager()

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        return {
            "id": self.id,
            "username": self.username,
            "allowance": self.allowance,
            "max_video_size": self.max_video_size,
        }

    def __str__(self):
        return self.username


class Video(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE
    )
    name = models.CharField(max_length=256)
    file = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    ext = models.CharField(max_length=256)
    date = models.DateTimeField(auto_now_add=True)
    # some extracted meta information
    fps = models.FloatField(blank=True, null=True)
    duration = models.FloatField(blank=True, null=True)
    height = models.IntegerField(blank=True, null=True)
    width = models.IntegerField(blank=True, null=True)

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        return {
            "name": self.name,
            "file": self.file.hex,
            "id": self.id.hex,
            "ext": self.ext,
            "date": self.date,
            "fps": self.fps,
            "duration": self.duration,
            "height": self.height,
            "width": self.width,
            "num_timelines": len(Timeline.objects.filter(video=self)),
        }

    def clone(self, owner=None, include_timelines=True, include_annotations=True):
        video_dict = self.to_dict(include_refs_hashes=False, include_refs=False)
        del video_dict["id"]
        if owner is not None:
            video_dict["owner"] = owner

        new_video_db = Video.objects.create(**video_dict)
        if include_timelines:
            for timeline in Timeline.objects.filter(video=self):
                timeline.clone(
                    video=new_video_db, include_annotations=include_annotations
                )

        return new_video_db  # FIXME


@receiver(post_delete, sender=Video)
def delete_video_file(sender, instance, **kwargs):
    logger.info(f"Deleting video {instance.id.hex} by user {instance.owner.username}")
    path = media_path_to_video(instance.id.hex, instance.ext)
    if os.path.exists(path):
        os.remove(path)


class Plugin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
        }
        return result


class PluginRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=256)
    progress = models.FloatField(default=0.0)
    in_scheduler = models.BooleanField(default=False)

    STATUS_UNKNOWN = "U"
    STATUS_ERROR = "E"
    STATUS_DONE = "D"
    STATUS_RUNNING = "R"
    STATUS_QUEUED = "Q"
    STATUS_WAITING = "W"
    STATUS = {
        STATUS_UNKNOWN: "UNKNOWN",
        STATUS_ERROR: "ERROR",
        STATUS_DONE: "DONE",
        STATUS_RUNNING: "RUNNING",
        STATUS_QUEUED: "QUEUED",
        STATUS_WAITING: "WAITING",
    }

    status = models.CharField(
        max_length=2,
        choices=[(k, v) for k, v in STATUS.items()],
        default=STATUS_UNKNOWN,
    )

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
            "type": self.type,
            "date": self.date,
            "update_date": self.update_date,
            "progress": self.progress,
            "status": self.STATUS[self.status],
        }
        if include_refs_hashes:
            result["video_id"] = self.video.id.hex
        return result


class PluginRunResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plugin_run = models.ForeignKey(
        PluginRun, on_delete=models.CASCADE, related_name="results"
    )
    name = models.CharField(max_length=256)
    data_id = models.CharField(null=True, max_length=64)
    TYPE_VIDEO = "V"
    TYPE_IMAGES = "I"
    TYPE_SCALAR = "S"
    TYPE_HIST = "H"
    TYPE_SHOTS = "SH"
    TYPE_RGB_HIST = "R"
    TYPE_CLUSTER = "CL"
    TYPE_FACE = "FA"
    TYPE_IMAGE_EMBEDDINGS = "E"
    TYPE = {
        TYPE_VIDEO: "VIDEO",
        TYPE_IMAGES: "IMAGES",
        TYPE_SCALAR: "SCALAR",
        TYPE_HIST: "HIST",
        TYPE_SHOTS: "SHOTS",
        TYPE_RGB_HIST: "RGB_HIST",
        TYPE_CLUSTER: "CLUSTER",
        TYPE_FACE: "FACE",
        TYPE_IMAGE_EMBEDDINGS: "IMAGE_EMBEDDINGS",
    }

    type = models.CharField(
        max_length=2,
        choices=[(k, v) for k, v in TYPE.items()],
        default=TYPE_SCALAR,
    )

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
            "type": self.TYPE[self.type],
            "data_id": self.data_id,
        }
        if include_refs_hashes:
            result["plugin_run_id"] = self.plugin_run.id.hex
        return result


@receiver(post_delete, sender=PluginRunResult)
def delete_pluginresult_data(sender, instance, **kwargs):
    logger.info(
        f"Deleting PluginRunResult {instance.id} by user {instance.plugin_run.video.owner.username}"
    )
    data_manager = DataManager("/predictions/")

    if instance.type == PluginRunResult.TYPE_IMAGES:
        data = data_manager.load(instance.data_id)
        try:
            with data:
                data.load()
            images = data.images
        except AttributeError:
            images = []
        for image in images:
            path = data_manager._create_file_path(image.id, image.ext)
            if os.path.exists(path):
                os.remove(path)

    for clusteritem in instance.cluster_items.all():
        filename, ext = clusteritem.image_path.split("/")[-1].split(".")

        path = data_manager._create_file_path(filename, ext)
        if os.path.exists(path):
            os.remove(path)

    data_manager.delete(instance.data_id)


class Timeline(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    plugin_run_result = models.ForeignKey(
        PluginRunResult, on_delete=models.CASCADE, null=True, blank=True
    )
    name = models.CharField(max_length=256)

    TYPE_ANNOTATION = "A"
    TYPE_PLUGIN_RESULT = "R"
    TYPE_TRANSCRIPT = "T"
    TYPE = {
        TYPE_ANNOTATION: "ANNOTATION",
        TYPE_PLUGIN_RESULT: "PLUGIN_RESULT",
        TYPE_TRANSCRIPT: "TRANSCRIPT",
    }

    type = models.CharField(
        max_length=2,
        choices=[(k, v) for k, v in TYPE.items()],
        default=TYPE_ANNOTATION,
    )
    order = models.IntegerField(default=-1)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True)
    collapse = models.BooleanField(default=False)

    VISUALIZATION_COLOR = "C"
    VISUALIZATION_CATEGORY_COLOR = "CC"
    VISUALIZATION_SCALAR_COLOR = "SC"
    VISUALIZATION_SCALAR_LINE = "SL"
    VISUALIZATION_HIST = "H"
    VISUALIZATION = {
        VISUALIZATION_COLOR: "COLOR",
        VISUALIZATION_CATEGORY_COLOR: "CATEGORY_COLOR",
        VISUALIZATION_SCALAR_COLOR: "SCALAR_COLOR",
        VISUALIZATION_SCALAR_LINE: "SCALAR_LINE",
        VISUALIZATION_HIST: "HIST",
    }
    visualization = models.CharField(
        max_length=2,
        choices=[(k, v) for k, v in VISUALIZATION.items()],
        default=VISUALIZATION_COLOR,
    )
    colormap = models.CharField(max_length=256, null=True, blank=True)
    colormap_inverse = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.order < 0:
            self.order = Timeline.objects.filter(video=self.video).count()

        super(Timeline, self).save(*args, **kwargs)

    class Meta:
        ordering = ["order"]

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
            "video_id": self.video.id.hex,
            "name": self.name,
            "type": self.TYPE[self.type],
            "visualization": self.VISUALIZATION[self.visualization],
            "order": self.order,
            "collapse": self.collapse,
            "colormap": self.colormap,
            "colormap_inverse": self.colormap_inverse,
        }

        if self.parent:
            result["parent_id"] = self.parent.id.hex
        else:
            result["parent_id"] = None

        if include_refs_hashes:
            result["timeline_segment_ids"] = [
                x.id.hex for x in self.timelinesegment_set.all()
            ]
            if self.plugin_run_result:
                result["plugin_run_result_id"] = self.plugin_run_result.id.hex

        elif include_refs:
            result["timeline_segments"] = [
                x.to_dict(
                    include_refs_hashes=include_refs_hashes,
                    include_refs=include_refs,
                    **kwargs,
                )
                for x in self.timelinesegment_set.all()
            ]
        return result

    def clone(self, video=None, include_annotations=True):
        if not video:
            video = self.video
        new_timeline_db = Timeline.objects.create(
            video=video, name=self.name, type=self.type
        )

        timeline_segment_added = []
        timeline_segment_annotations_added = []
        for segment in self.timelinesegment_set.all():
            result = segment.clone(new_timeline_db, include_annotations)
            timeline_segment_added.extend(result["timeline_segment_added"])
            timeline_segment_annotations_added.extend(
                result["timeline_segment_annotation_added"]
            )

        return {
            "timeline_added": new_timeline_db,
            "timeline_segment_added": timeline_segment_added,
            "timeline_segment_annotation_added": timeline_segment_annotations_added,
        }


class AnnotationCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, blank=True, null=True, on_delete=models.CASCADE)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE
    )
    name = models.CharField(max_length=256)
    color = models.CharField(max_length=256, default=random_color_string)

    def to_dict(self, **kwargs):
        result = {
            "id": self.id.hex,
            "name": self.name,
            "color": self.color,
        }
        return result


class Annotation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        AnnotationCategory, on_delete=models.CASCADE, null=True
    )
    video = models.ForeignKey(Video, blank=True, null=True, on_delete=models.CASCADE)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE
    )
    name = models.CharField(max_length=1024)
    color = models.CharField(max_length=256, default=random_color_string)

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
            "name": self.name,
            "color": self.color,
        }
        if include_refs_hashes and self.category:
            result["category_id"] = self.category.id.hex
        elif include_refs and self.category:
            result["category"] = self.category.to_dict(
                include_refs_hashes=True, include_refs=False, **kwargs
            )
        return result


class TimelineSegment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timeline = models.ForeignKey(Timeline, on_delete=models.CASCADE)
    annotations = models.ManyToManyField(
        Annotation, through="TimelineSegmentAnnotation"
    )
    color = models.CharField(max_length=256, null=True)
    start = models.FloatField(default=0)
    end = models.FloatField(default=0)

    class Meta:
        ordering = ["start"]

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
            "timeline_id": self.timeline.id.hex,
            "color": self.color,
            "start": self.start,
            "end": self.end,
        }
        if include_refs_hashes:
            result["annotation_ids"] = [x.id.hex for x in self.annotations.all()]
        if include_refs:
            result["annotations"] = [
                x.to_dict(include_refs_hashes=True, include_refs=False, **kwargs)
                for x in self.annotations.all()
            ]
        return result

    def clone(self, timeline=None, include_annotations=True):
        if not timeline:
            timeline = self.timeline
        new_timeline_segment_db = TimelineSegment.objects.create(
            timeline=timeline, color=self.color, start=self.start, end=self.end
        )

        if not include_annotations:
            return new_timeline_segment_db

        timeline_segment_annotation_added = []
        for annotation in self.timelinesegmentannotation_set.all():
            timeline_segment_annotation_added.extend(
                annotation.clone(new_timeline_segment_db)[
                    "timeline_segment_annotation_added"
                ]
            )

        return {
            "timeline_segment_added": [new_timeline_segment_db],
            "timeline_segment_annotation_added": timeline_segment_annotation_added,
        }


# This is basically a many to many connection
class TimelineSegmentAnnotation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timeline_segment = models.ForeignKey(TimelineSegment, on_delete=models.CASCADE)
    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)

    def to_dict(self, include_refs_hashes=True, **kwargs):
        result = {
            "id": self.id.hex,
            "date": self.date,
        }
        if include_refs_hashes:
            result["annotation_id"] = self.annotation.id.hex
            result["timeline_segment_id"] = self.timeline_segment.id.hex
        return result

    def clone(self, timeline_segment):
        new_timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.create(
            timeline_segment=timeline_segment,
            annotation=self.annotation,
        )
        return {
            "timeline_segment_annotation_added": [new_timeline_segment_annotation_db]
        }


class Shortcut(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, blank=True, null=True, on_delete=models.CASCADE)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE
    )
    type = models.CharField(max_length=256, null=True)
    keys = models.JSONField(null=True)
    keys_string = models.CharField(max_length=256, null=True)

    date = models.DateTimeField(auto_now_add=True)

    def to_dict(self, include_refs_hashes=True, **kwargs):
        result = {
            "id": self.id.hex,
            "date": self.date,
            "type": self.type,
            "keys": self.keys,
        }
        if include_refs_hashes:
            result["video_id"] = self.video.id.hex
        return result

    @classmethod
    def generate_keys_string(cls, keys):
        keys = set([x.lower() for x in keys])
        keys_string = []
        if "ctrl" in keys:
            keys_string.append("ctrl")
            keys.remove("ctrl")
        if "shift" in keys:
            keys_string.append("shift")
            keys.remove("shift")
        for key in keys:
            keys_string.append(key)

        return "+".join(keys_string)


class AnnotationShortcut(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shortcut = models.ForeignKey(Shortcut, on_delete=models.CASCADE)
    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)

    def to_dict(self, include_refs_hashes=True, **kwargs):
        result = {
            "id": self.id.hex,
            "date": self.date,
        }
        if include_refs_hashes:
            result["shortcut_id"] = self.shortcut.id.hex
            result["annotation_id"] = self.annotation.id.hex
        return result


class ClusterTimelineItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plugin_run = models.ForeignKey(PluginRun, default=None, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, blank=True, null=True, on_delete=models.CASCADE)
    cluster_id = models.UUIDField(null=True, blank=True)
    name = models.CharField(max_length=256)

    TYPE_FACE = "A"
    TYPE_PLACE = "P"
    TYPE = {
        TYPE_FACE: "FACE",
        TYPE_PLACE: "PLACE",
    }

    type = models.CharField(
        max_length=2,
        choices=[(k, v) for k, v in TYPE.items()],
        default=TYPE_FACE,
    )

    def to_dict(self, include_refs_hashes=True, include_refs=False, **kwargs):
        result = {
            "id": self.id.hex,
            "name": self.name,
            "cluster_id": self.cluster_id.hex,
            "plugin_run": self.plugin_run.id.hex,
            "type": self.type,
            "items": [item.to_dict() for item in self.items.all()],
        }

        if self.video:
            result["video"] = self.video.id.hex

        return result


class ClusterItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cluster_timeline_item = models.ForeignKey(
        ClusterTimelineItem, on_delete=models.CASCADE, related_name="items"
    )
    video = models.ForeignKey(Video, null=True, on_delete=models.CASCADE)
    # plugin_item_ref = models.UUIDField()
    embedding_id = models.CharField(max_length=100)
    image_path = models.CharField(max_length=128, null=True)
    plugin_run_result = models.ForeignKey(
        PluginRunResult, on_delete=models.CASCADE, related_name="cluster_items"
    )
    time = models.FloatField()
    delta_time = models.FloatField()
    is_sample = models.BooleanField(default=False)

    TYPE_FACE = "A"
    TYPE_PLACE = "P"
    TYPE = {
        TYPE_FACE: "FACE",
        TYPE_PLACE: "PLACE",
    }

    type = models.CharField(
        max_length=2,
        choices=[(k, v) for k, v in TYPE.items()],
        default=TYPE_FACE,
    )

    def to_dict(self):
        result = {
            "id": self.id.hex,
            "image_path": self.image_path,
            "type": self.TYPE[self.type],
            "time": self.time,
            "delta_time": self.delta_time,
            "is_sample": self.is_sample,
        }

        return result


class VideoAnalysisState(models.Model):

    video = models.OneToOneField(
        Video,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    selected_shots = models.ForeignKey(
        Timeline,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    selected_place_clustering = models.ForeignKey(
        PluginRun,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="video_analyses_state_place_clustering",
    )
    selected_face_clustering = models.ForeignKey(
        PluginRun,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="video_analyses_state_face_clustering",
    )

    def to_dict(self):
        result = {
            "selected_shots": (
                self.selected_shots.id.hex if self.selected_shots else None
            ),
            "selected_place_clustering": (
                self.selected_place_clustering.id.hex
                if self.selected_place_clustering
                else None
            ),
            "selected_face_clustering": (
                self.selected_face_clustering.id.hex
                if self.selected_face_clustering
                else None
            ),
        }

        return result
