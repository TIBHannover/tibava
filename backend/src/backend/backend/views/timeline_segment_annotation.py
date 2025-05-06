import os
import shutil
import sys
import json
from time import time
import uuid
import logging
import traceback
import tempfile
from pathlib import Path

from urllib.parse import urlparse
import imageio
from numpy import isin
import time

import wand.image as wimage

from backend.utils import download_url, download_file, media_url_to_video

from django.views import View
from django.http import HttpResponse, JsonResponse
from django.conf import settings
# from django.core.exceptions import BadRequest

from backend.models import TimelineSegment, TimelineSegmentAnnotation, Annotation, AnnotationCategory


logger = logging.getLogger(__name__)


class TimelineSegmentAnnoatationCreate(View):
    def post(self, request):
        try:

            # decode data
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            # get segment
            try:
                segment_db = TimelineSegment.objects.get(id=data.get("timeline_segment_id"))
            except TimelineSegment.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            # link existing annotation
            if "annotation_id" in data:
                try:
                    annotation_db = Annotation.objects.get(id=data.get("annotation_id"))
                except Annotation.DoesNotExist:
                    return JsonResponse({"status": "error", "type": "not_exist"})
                if (
                    TimelineSegmentAnnotation.objects.filter(
                        timeline_segment=segment_db, annotation=annotation_db
                    ).count()
                    > 0
                ):
                    return JsonResponse({"status": "error", "type": "exist"})

                timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.create(
                    timeline_segment=segment_db, annotation=annotation_db
                )
                # if not created:
                #     return JsonResponse({"status": "error", "type": "creation_failed"})
                return JsonResponse({"status": "ok", "entry": timeline_segment_annotation_db.to_dict()})

            # create a annotation from exisitng categories
            elif "annotation_name" in data and "annotation_category_id" in data:
                try:
                    annotation_category_db = AnnotationCategory.objects.get(id=data.get("annotation_category_id"))
                except AnnotationCategory.DoesNotExist:
                    return JsonResponse({"status": "error", "type": "not_exist"})

                if "annotation_color" in data:

                    annotation_db = Annotation.objects.create(
                        category=annotation_category_db,
                        name=data.get("annotation_name"),
                        color=data.get("annotation_color"),
                    )
                else:
                    annotation_db = Annotation.objects.create(
                        category=annotation_category_db,
                        name=data.get("annotation_name"),
                    )

                timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.create(
                    timeline_segment=segment_db, annotation=annotation_db
                )
                # if not created:
                #     return JsonResponse({"status": "error", "type": "creation_failed"})
                return JsonResponse({"status": "ok", "entry": timeline_segment_annotation_db.to_dict()})

            elif "annotation_name" in data and "annotation_category_name" in data:
                if "annotation_category_color" in data:

                    annotation_category_db = AnnotationCategory.objects.create(
                        name=data.get("annotation_category_name"),
                        color=data.get("annotation_category_color"),
                    )
                else:
                    annotation_category_db = AnnotationCategory.objects.create(
                        name=data.get("annotation_category_name"),
                    )

                if "annotation_color" in data:
                    annotation_db = Annotation.objects.create(
                        category=annotation_category_db,
                        name=data.get("annotation_name"),
                        color=data.get("annotation_color"),
                    )
                else:
                    annotation_db = Annotation.objects.create(
                        category=annotation_category_db,
                        name=data.get("annotation_name"),
                    )

                timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.create(
                    timeline_segment=segment_db, annotation=annotation_db
                )
                # if not created:
                #     return JsonResponse({"status": "error", "type": "creation_failed"})
                return JsonResponse({"status": "ok", "entry": timeline_segment_annotation_db.to_dict()})

            return JsonResponse({"status": "error", "type": "missing_values"})
        except Exception:
            logger.exception("Failed to create timeline segment annotation")
            return JsonResponse({"status": "error"})


# from django.core.exceptions import BadRequest
class TimelineSegmentAnnoatationToggle(View):
    def parse_timeline_segment_ids(self, data):

        timeline_segment_ids = []
        if "timeline_segment_ids" in data:
            if not isinstance(data.get("timeline_segment_ids"), (list, set)):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            for timeline_segment_id in data.get("timeline_segment_ids"):
                if not isinstance(timeline_segment_id, str):
                    return JsonResponse({"status": "error", "type": "wrong_request_body"})
                timeline_segment_ids.append(timeline_segment_id)

        elif "timeline_segment_id" in data:
            if not isinstance(data.get("timeline_segment_id"), str):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})
            timeline_segment_ids.append(data.get("timeline_segment_id"))

        else:
            return JsonResponse({"status": "error", "type": "missing_values"})

        timeline_segment_dbs = []
        for timeline_segment_id in timeline_segment_ids:
            try:
                timeline_segment_db = TimelineSegment.objects.get(id=timeline_segment_id)
                timeline_segment_dbs.append(timeline_segment_db)
            except TimelineSegment.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

        return timeline_segment_dbs

    def parse_and_create_annotation(self, data):

        annotation_added = []
        annotation_category_added = []
        # link existing annotation
        if "annotation_id" in data:
            try:
                annotation_db = Annotation.objects.get(id=data.get("annotation_id"))
            except Annotation.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})
            return annotation_db, annotation_added, annotation_category_added
        # create a annotation from exisitng categories
        elif "annotation_name" in data and "annotation_category_id" in data:
            try:
                annotation_category_db = AnnotationCategory.objects.get(id=data.get("annotation_category_id"))
            except AnnotationCategory.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            if "annotation_color" in data:

                annotation_db = Annotation.objects.create(
                    category=annotation_category_db,
                    name=data.get("annotation_name"),
                    color=data.get("annotation_color"),
                )
            else:
                annotation_db = Annotation.objects.create(
                    category=annotation_category_db,
                    name=data.get("annotation_name"),
                )

            annotation_added.append(annotation_db.to_dict())

            return annotation_db, annotation_added, annotation_category_added

        elif "annotation_name" in data and "annotation_category_name" in data:
            if "annotation_category_color" in data:

                annotation_category_db = AnnotationCategory.objects.create(
                    name=data.get("annotation_category_name"),
                    color=data.get("annotation_category_color"),
                )
            else:
                annotation_category_db = AnnotationCategory.objects.create(
                    name=data.get("annotation_category_name"),
                )
            annotation_category_added.append(annotation_category_db.to_dict())

            if "annotation_color" in data:
                annotation_db = Annotation.objects.create(
                    category=annotation_category_db,
                    name=data.get("annotation_name"),
                    color=data.get("annotation_color"),
                )
            else:
                annotation_db = Annotation.objects.create(
                    category=annotation_category_db,
                    name=data.get("annotation_name"),
                )

            annotation_added.append(annotation_db.to_dict())

            return annotation_db, annotation_added, annotation_category_added
        return JsonResponse({"status": "error", "type": "missing_values"})

    def post(self, request):
        start = time.time()
        try:

            # decode data
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            # get segment
            timeline_segment_dbs = self.parse_timeline_segment_ids(data)
            if isinstance(timeline_segment_dbs, JsonResponse):
                return timeline_segment_dbs

            # get or create annotation
            result = self.parse_and_create_annotation(data)
            if isinstance(result, JsonResponse):
                return result
            annotation_db, annotation_added, annotation_category_added = result

            timeline_segment_annotation_deleted = []
            timeline_segment_annotation_added = []
            for timeline_segment_db in timeline_segment_dbs:

                try:
                    timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.get(
                        timeline_segment=timeline_segment_db, annotation=annotation_db
                    )
                    timeline_segment_annotation_deleted.append(timeline_segment_annotation_db.id.hex)
                    timeline_segment_annotation_db.delete()
                except TimelineSegmentAnnotation.DoesNotExist:
                    timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.create(
                        timeline_segment=timeline_segment_db, annotation=annotation_db
                    )

                    timeline_segment_annotation_added.append(timeline_segment_annotation_db.to_dict())
                except TimelineSegmentAnnotation.MultipleObjectsReturned:

                    timeline_segment_annotation_db = TimelineSegmentAnnotation.objects.filter(
                        timeline_segment=timeline_segment_db, annotation=annotation_db
                    )
                    timeline_segment_annotation_deleted.extend([x.id.hex for x in timeline_segment_annotation_db])
                    timeline_segment_annotation_db.delete()

            end = time.time()
            logger.debug(f"Timeline annotation toggle request took {end-start}s")
            return JsonResponse(
                {
                    "status": "ok",
                    "annotation_added": annotation_added,
                    "annotation_category_added": annotation_category_added,
                    "timeline_segment_annotation_deleted": timeline_segment_annotation_deleted,
                    "timeline_segment_annotation_added": timeline_segment_annotation_added,
                }
            )

        except Exception:
            logger.exception('Failed to load timeline annotation toggle')
            return JsonResponse({"status": "error"})


class TimelineSegmentAnnoatationList(View):
    def get(self, request):
        try:
            start = time.time()
            query_args = {}

            if "timeline_segment_id" in request.GET:
                query_args["timeline_segment_set__id"] = request.GET.get("timeline_segment_id")

            if "video_id" in request.GET:
                query_args["timeline_segment__timeline__video__id"] = request.GET.get("video_id")

            query_results = (
                TimelineSegmentAnnotation.objects.filter(**query_args)
                .select_related("timeline_segment")
                .select_related("annotation")
            )

            entries = []
            for timeline_segment_annotation in query_results:
                entries.append(timeline_segment_annotation.to_dict())

            end = time.time()
            logger.debug(f"Getting TimelineSegmentAnnotationList took {end-start}s")
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception('Failed to get timeline annotations')
            return JsonResponse({"status": "error"})


# from django.core.exceptions import BadRequest
class TimelineSegmentAnnoatationDelete(View):
    def post(self, request):
        try:

            # decode data
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            # get segment
            num_deleted = 0
            try:
                num_deleted, _ = TimelineSegmentAnnotation.objects.get(
                    id=data.get("timeline_segment_annotation_id")
                ).delete()
            except TimelineSegment.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})
            logger.debug(f'Deleted {num_deleted} timeline annotations')
            if num_deleted == 1:
                return JsonResponse({"status": "ok"})
            return JsonResponse({"status": "error"})

        except Exception:
            logger.exception("Failed to delete timeline segment annotation")
            return JsonResponse({"status": "error"})
