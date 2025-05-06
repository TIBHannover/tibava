import json
import logging
import traceback
from unicodedata import category


from django.views import View
from django.http import JsonResponse

from backend.models import Annotation, AnnotationCategory, Video


logger = logging.getLogger(__name__)


# from django.core.exceptions import BadRequest
class AnnoatationCreate(View):
    def post(self, request):
        try:

            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})
            # decode data
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            if "name" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            try:
                query_args = {"name": data.get("name"), "owner": request.user}
                if "category_id" in data:
                    query_args["category__id"] = data.get("category_id")
                if "video_id" in data:
                    query_args["video__id"] = data.get("video_id")
                annotation_db = Annotation.objects.get(**query_args)
            except Annotation.DoesNotExist:
                create_args = {"name": data.get("name"), "owner": request.user}
                if "color" in data:
                    create_args["color"] = data.get("color")
                if "video_id" in data:
                    try:
                        video_db = Video.objects.get(id=data.get("video_id"))
                    except Video.DoesNotExist:
                        return JsonResponse({"status": "error", "type": "not_exist"})
                    create_args["video"] = video_db

                if "category_id" in data:
                    try:
                        annotation_category_db = AnnotationCategory.objects.get(id=data.get("category_id"))
                    except AnnotationCategory.DoesNotExist:
                        return JsonResponse({"status": "error", "type": "not_exist"})
                    create_args["category"] = annotation_category_db

                annotation_db = Annotation.objects.create(**create_args)

            return JsonResponse({"status": "ok", "entry": annotation_db.to_dict()})
        except Exception:
            logger.exception('Failed to create annotation')
            return JsonResponse({"status": "error"})


# from django.core.exceptions import BadRequest
class AnnoatationChange(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            # decode data
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            update_args = {}
            if "category_id" in data:
                try:
                    annotation_category_db = AnnotationCategory.objects.get(id=data.get("category_id"))
                    update_args["category"] = annotation_category_db
                except AnnotationCategory.DoesNotExist:
                    return JsonResponse({"status": "error", "type": "not_exist"})

            if "annotation_id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            if "name" in data:
                update_args["name"] = data.get("name")

            if "color" in data:
                update_args["color"] = data.get("color")
            updated = Annotation.objects.filter(id=data.get("annotation_id")).update(**update_args)
            if updated != 1:
                return JsonResponse({"status": "error"})

            return JsonResponse({"status": "ok"})
        except Exception:
            logger.exception('Failed to change annotation')
            return JsonResponse({"status": "error"})


class AnnoatationList(View):
    def get(self, request):
        try:

            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            query_args = {}

            query_args["owner"] = request.user

            if "video_id" in request.GET:
                query_args["video__id"] = request.GET.get("video_id")

            query_results = Annotation.objects.filter(**query_args)

            entries = []
            for annotation in query_results:
                entries.append(annotation.to_dict())
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception('Failed to list annotations')
            return JsonResponse({"status": "error"})
