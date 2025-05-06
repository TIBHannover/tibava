import os
import shutil
import sys
import json
from typing import Dict
import uuid
import logging
import traceback
import tempfile
from pathlib import Path

from urllib.parse import urlparse
import imageio

import wand.image as wimage

from backend.utils import download_url, download_file, media_url_to_video

from django.views import View
from django.http import HttpResponse, JsonResponse
from django.conf import settings
import time

# from django.core.exceptions import BadRequest

from backend.models import AnnotationCategory, Annotation, TimelineSegment, TimelineSegmentAnnotation, Timeline


logger = logging.getLogger(__name__)


class TimelineSegmentAnnotate(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                logger.error("TimelineSegmentAnnotate::not_authenticated")
                return JsonResponse({"status": "error"})

            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error"})

            timeline_segment_ids = data.get("timeline_segment_ids")
            try:
                segment_dbs = TimelineSegment.objects.filter(id__in=timeline_segment_ids)
                if len(segment_dbs) != len(timeline_segment_ids):
                    return JsonResponse({"status": "error", "type": "not_exist"})

                if len(segment_dbs) <= 0:
                    return JsonResponse({"status": "error", "type": "not_exist"})

            except TimelineSegment.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            # TODO check if it is the same video
            video_db = segment_dbs[0].timeline.video

            # delete all existing annotation for this segment
            timeline_segment_annotation_deleted = [
                x.id.hex for x in TimelineSegmentAnnotation.objects.filter(timeline_segment_id__in=timeline_segment_ids)
            ]
            TimelineSegmentAnnotation.objects.filter(timeline_segment__in=timeline_segment_ids).delete()

            timeline_segment_annotation_added = []
            annotation_added = []
            annotation_category_added = []
            if "annotations" in data and isinstance(data.get("annotations"), (list, set)):
                for annotation in data.get("annotations"):
                    # check if there is a category with this name for this video
                    # TODO check name and color in dict
                    annotation_category_db = None
                    if "category" in annotation and isinstance(annotation.get("category"), Dict):
                        category = annotation.get("category")
                        try:
                            annotation_category_db = AnnotationCategory.objects.get(
                                video=video_db, name=category.get("name"), owner=request.user
                            )
                        except AnnotationCategory.DoesNotExist:
                            annotation_category_db = AnnotationCategory.objects.create(
                                name=category.get("name"),
                                color=category.get("color"),
                                video=video_db,
                                owner=request.user,
                            )
                            annotation_category_added.append(annotation_category_db.to_dict())

                    # check if there is a existing annotation with this name and category for this video
                    # TODO check name and color in dict
                    query_dict = {"video": video_db, "name": annotation.get("name"), "owner": request.user}
                    if annotation_category_db:
                        query_dict["category"] = annotation_category_db
                    else:
                        query_dict["category"] = None
                    try:
                        annotation_db = Annotation.objects.get(**query_dict)
                    except Annotation.DoesNotExist:
                        annotation_db = Annotation.objects.create(**{**query_dict, "color": annotation.get("color")})
                        annotation_added.append(annotation_db.to_dict())
                    for segment_db in segment_dbs:
                        timeline_segment_annotation_db, created = TimelineSegmentAnnotation.objects.get_or_create(
                            timeline_segment=segment_db, annotation=annotation_db
                        )
                        if created:
                            timeline_segment_annotation_added.append(timeline_segment_annotation_db.to_dict())
            # query_args = {}

            # query_args["timeline__video__owner"] = request.user

            # if "timeline_id" in request.GET:
            #     query_args["timeline__id"] = request.GET.get("timeline_id")

            # if "video_id" in request.GET:
            #     query_args["timeline__video__id"] = request.GET.get("video_id")

            # timeline_segments = TimelineSegment.objects.filter(**query_args)

            # entries = []
            # for segment in timeline_segments:
            #     entries.append(segment.to_dict())
            return JsonResponse(
                {
                    "status": "ok",
                    "timeline_segment_annotation_deleted": timeline_segment_annotation_deleted,
                    "timeline_segment_annotation_added": timeline_segment_annotation_added,
                    "annotation_category_added": annotation_category_added,
                    "annotation_added": annotation_added,
                }
            )
        except Exception:
            logger.exception("Failed to annotate timeline segment")
            return JsonResponse({"status": "error"})


class TimelineSegmentAnnotateRange(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                logger.error("VideoUpload::not_authenticated")
                return JsonResponse({"status": "error"})

            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error"})
            if "start" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if "end" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if "timeline_id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if "annotations" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            try:
                timeline_db = Timeline.objects.get(id=data.get("timeline_id"))

            except Timeline.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            # TODO check if it is the same video
            video_db = timeline_db.video

            # first find everything between
            timeline_segment_dbs = TimelineSegment.objects.filter(
                timeline=timeline_db, start__gte=data.get("start"), end__lte=data.get("end")
            )
            # for x in timeline_segment_dbs:
            #     print(x.to_dict())
            # print(timeline_segment_dbs)
            timeline_segment_ids = [x.id for x in timeline_segment_dbs]

            # left segment
            left_timeline_segment_dbs = TimelineSegment.objects.filter(
                timeline=timeline_db, start__lte=data.get("start"), end__gte=data.get("start")
            )
            # right segment
            right_timeline_segment_dbs = TimelineSegment.objects.filter(
                timeline=timeline_db, start__lte=data.get("end"), end__gte=data.get("end")
            )

            # delete all old stuff
            timeline_segment_deleted = []
            timeline_segment_deleted.extend([x.id.hex for x in timeline_segment_dbs])
            timeline_segment_deleted.extend([x.id.hex for x in left_timeline_segment_dbs])
            timeline_segment_deleted.extend([x.id.hex for x in right_timeline_segment_dbs])
            timeline_segment_deleted = list(set(timeline_segment_deleted))

            # clone new sgements
            timeline_segment_added = []
            timeline_segment_annotation_added = []
            annotation_added = []
            annotation_category_added = []
            # Move everything to the left and right
            if len(left_timeline_segment_dbs) == 1 and len(right_timeline_segment_dbs) == 1:
                if left_timeline_segment_dbs[0].id == right_timeline_segment_dbs[0].id:
                    right_timeline_segment_db = left_timeline_segment_dbs[0].clone()["timeline_segment_added"][0]
                    right_timeline_segment_db.start = data.get("end")
                    right_timeline_segment_db.save()

                    timeline_segment_annotation_added.extend(
                        [x.to_dict() for x in right_timeline_segment_db.timelinesegmentannotation_set.all()]
                    )

                    left_timeline_segment_dbs[0].end = data.get("start")
                    left_timeline_segment_dbs[0].save()
                    timeline_segment_added.append(left_timeline_segment_dbs[0].to_dict())
                    timeline_segment_added.append(right_timeline_segment_db.to_dict())
                else:
                    left_timeline_segment_dbs.update(end=data.get("start"))
                    right_timeline_segment_dbs.update(start=data.get("end"))
                    timeline_segment_added.extend([x.to_dict() for x in left_timeline_segment_dbs])
                    timeline_segment_added.extend([x.to_dict() for x in right_timeline_segment_dbs])
            else:
                left_timeline_segment_dbs.update(end=data.get("start"))
                right_timeline_segment_dbs.update(start=data.get("end"))
                timeline_segment_added.extend([x.to_dict() for x in left_timeline_segment_dbs])
                timeline_segment_added.extend([x.to_dict() for x in right_timeline_segment_dbs])

            timeline_segment_annotation_deleted = [
                x.id.hex for x in TimelineSegmentAnnotation.objects.filter(timeline_segment_id__in=timeline_segment_ids)
            ]

            TimelineSegmentAnnotation.objects.filter(timeline_segment__in=timeline_segment_ids).delete()

            timeline_segment_dbs.delete()
            timeline_segment_db = TimelineSegment.objects.create(
                timeline=timeline_db, start=data.get("start"), end=data.get("end")
            )

            if "annotations" in data and isinstance(data.get("annotations"), (list, set)):
                for annotation in data.get("annotations"):
                    # check if there is a category with this name for this video
                    # TODO check name and color in dict
                    annotation_category_db = None
                    if "category" in annotation and isinstance(annotation.get("category"), Dict):
                        category = annotation.get("category")
                        try:
                            annotation_category_db = AnnotationCategory.objects.get(
                                video=video_db, name=category.get("name"), owner=request.user
                            )
                        except AnnotationCategory.DoesNotExist:
                            annotation_category_db = AnnotationCategory.objects.create(
                                name=category.get("name"),
                                color=category.get("color"),
                                video=video_db,
                                owner=request.user,
                            )
                            annotation_category_added.append(annotation_category_db.to_dict())

                    # check if there is a existing annotation with this name and category for this video
                    # TODO check name and color in dict
                    query_dict = {"video": video_db, "name": annotation.get("name"), "owner": request.user}
                    if annotation_category_db:
                        query_dict["category"] = annotation_category_db
                    else:
                        query_dict["category"] = None
                    try:
                        annotation_db = Annotation.objects.get(**query_dict)
                    except Annotation.DoesNotExist:
                        annotation_db = Annotation.objects.create(**{**query_dict, "color": annotation.get("color")})
                        annotation_added.append(annotation_db.to_dict())
                    timeline_segment_annotation_db, created = TimelineSegmentAnnotation.objects.get_or_create(
                        timeline_segment=timeline_segment_db, annotation=annotation_db
                    )
                    if created:
                        timeline_segment_annotation_added.append(timeline_segment_annotation_db.to_dict())

            timeline_segment_added.append(timeline_segment_db.to_dict())
            return JsonResponse(
                {
                    "status": "ok",
                    "timeline_segment_annotation_deleted": timeline_segment_annotation_deleted,
                    "timeline_segment_annotation_added": timeline_segment_annotation_added,
                    "annotation_category_added": annotation_category_added,
                    "annotation_added": annotation_added,
                    "timeline_segment_deleted": timeline_segment_deleted,
                    "timeline_segment_added": timeline_segment_added,
                }
            )
        except Exception:
            logger.exception("Failed to annotate timeline segment range")
            return JsonResponse({"status": "error"})


class TimelineSegmentGet(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            query_args = {}

            query_args["timeline__video__owner"] = request.user

            if "timeline_id" in request.GET:
                query_args["timeline__id"] = request.GET.get("timeline_id")

            if "video_id" in request.GET:
                query_args["timeline__video__id"] = request.GET.get("video_id")

            timeline_segments = TimelineSegment.objects.filter(**query_args).order_by("start")

            entries = []
            for segment in timeline_segments:
                entries.append(segment.to_dict())
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception("Failed to get timeline segment")
            return JsonResponse({"status": "error"})


class TimelineSegmentList(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            query_args = {}

            query_args["timeline__video__owner"] = request.user

            if "timeline_id" in request.GET:
                query_args["timeline__id"] = request.GET.get("timeline_id")

            if "video_id" in request.GET:
                query_args["timeline__video__id"] = request.GET.get("video_id")

            timeline_segments = (
                TimelineSegment.objects.filter(**query_args).select_related("timeline").prefetch_related("annotations")
            )
            entries = []
            for segment in timeline_segments:
                entries.append(segment.to_dict())
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception("Failed to list timeline segments")
            return JsonResponse({"status": "error"})


class TimelineSegmentMerge(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                logger.error("VideoUpload::not_authenticated")
                return JsonResponse({"status": "error"})

            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error"})

            if "timeline_segment_ids" not in data or not isinstance(data.get("timeline_segment_ids"), (list, set)):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            timeline_segments = []
            for id in data.get("timeline_segment_ids"):
                try:
                    timeline_segment_db = TimelineSegment.objects.get(id=id)
                    timeline_segments.append(timeline_segment_db)
                except TimelineSegment.DoesNotExist:
                    return JsonResponse({"status": "error", "type": "not_exist"})

            if len(timeline_segments) < 2:
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            if not all([x.timeline.id == timeline_segments[0].timeline.id for x in timeline_segments]):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            # get some information for query and the new segment
            start = min([x.start for x in timeline_segments])
            end = max([x.end for x in timeline_segments])
            timeline = timeline_segments[0].timeline.id
            color = timeline_segments[0].timeline.id

            timeline_segment_dbs = TimelineSegment.objects.filter(
                start__gte=start, timeline__id=timeline_segments[0].timeline.id, end__lte=end
            )

            timeline_segment_deleted = []
            timeline_segment_added = []
            timeline_segment_annotation_deleted = []
            timeline_segment_annotation_added = []

            # get all annotations from this block and delete all segments
            annotations = []
            for timeline_segment_db in timeline_segment_dbs:
                annotations.extend([x.annotation.id for x in timeline_segment_db.timelinesegmentannotation_set.all()])
                timeline_segment_annotation_deleted.extend(
                    [x.id.hex for x in timeline_segment_db.timelinesegmentannotation_set.all()]
                )
                timeline_segment_deleted.append(timeline_segment_db.id.hex)
                timeline_segment_db.delete()
            annotations = list(set(annotations))

            timeline_segment_db = TimelineSegment.objects.create(
                timeline=Timeline.objects.get(id=timeline), color=color, start=start, end=end
            )

            timeline_segment_annotation_dbs = []
            for annotation in annotations:
                timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.create(
                    timeline_segment=timeline_segment_db, annotation=Annotation.objects.get(id=annotation)
                )
                timeline_segment_annotation_dbs.append(timeline_segment_annotation_db)

            timeline_segment_added.append(timeline_segment_db.to_dict())
            timeline_segment_annotation_added.extend([x.to_dict() for x in timeline_segment_annotation_dbs])

            return JsonResponse(
                {
                    "status": "ok",
                    "timeline_segment_deleted": timeline_segment_deleted,
                    "timeline_segment_added": timeline_segment_added,
                    "timeline_segment_annotation_deleted": timeline_segment_annotation_deleted,
                    "timeline_segment_annotation_added": timeline_segment_annotation_added,
                }
            )
        except Exception:
            logger.exception("Failed to merge timeline segments")
            return JsonResponse({"status": "error"})


class TimelineSegmentSplit(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error"})
            if "timeline_segment_id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            if "time" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            if not isinstance(data.get("time"), (float, int)):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            timeline_segment_deleted = []
            timeline_segment_added = []
            timeline_segment_annotation_deleted = []
            timeline_segment_annotation_added = []

            try:
                timeline_segment_db = TimelineSegment.objects.get(id=data.get("timeline_segment_id"))
            except TimelineSegment.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            if timeline_segment_db.start > data.get("time") and timeline_segment_db.end < data.get("time"):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            timeline_segment_db_splits = [
                timeline_segment_db.clone()["timeline_segment_added"][0],
                timeline_segment_db.clone()["timeline_segment_added"][0],
            ]
            timeline_segment_db_splits[0].end = data.get("time")
            timeline_segment_db_splits[1].start = data.get("time")
            timeline_segment_db_splits[0].save()
            timeline_segment_db_splits[1].save()

            timeline_segment_added.append(timeline_segment_db_splits[0].to_dict())
            timeline_segment_added.append(timeline_segment_db_splits[1].to_dict())

            timeline_segment_annotation_added.extend(
                [x.to_dict() for x in timeline_segment_db_splits[0].timelinesegmentannotation_set.all()]
            )
            timeline_segment_annotation_added.extend(
                [x.to_dict() for x in timeline_segment_db_splits[1].timelinesegmentannotation_set.all()]
            )

            timeline_segment_deleted.append(timeline_segment_db.id.hex)
            timeline_segment_annotation_deleted.extend(
                [x.id.hex for x in timeline_segment_db.timelinesegmentannotation_set.all()]
            )
            timeline_segment_db.delete()

            return JsonResponse(
                {
                    "status": "ok",
                    "timeline_segment_deleted": timeline_segment_deleted,
                    "timeline_segment_added": timeline_segment_added,
                    "timeline_segment_annotation_deleted": timeline_segment_annotation_deleted,
                    "timeline_segment_annotation_added": timeline_segment_annotation_added,
                }
            )
        except Exception:
            logger.exception("Failed to split timeline segment")
            return JsonResponse({"status": "error"})


# class TimelineSegmentDelete(View):
#     def post(self, request):
#         try:
#             try:
#                 body = request.body.decode("utf-8")
#             except (UnicodeDecodeError, AttributeError):
#                 body = request.body

#             try:
#                 data = json.loads(body)
#             except Exception as e:
#                 return JsonResponse({"status": "error"})
#             count, _ = Timeline.objects.filter(id=data.get("id")).delete()
#             if count:
#                 return JsonResponse({"status": "ok"})
#             return JsonResponse({"status": "error"})
#         except Exception as e:
#             logger.error(traceback.format_exc())
#             return JsonResponse({"status": "error"})
