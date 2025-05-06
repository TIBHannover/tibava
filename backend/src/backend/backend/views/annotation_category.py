import json
import logging
import traceback


from django.views import View
from django.http import JsonResponse

from backend.models import AnnotationCategory, Video


logger = logging.getLogger(__name__)


# from django.core.exceptions import BadRequest
class AnnoatationCategoryCreate(View):
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
                if "video_id" in data:
                    query_args["video__id"] = data.get("video_id")
                annotation_category_db = AnnotationCategory.objects.get(**query_args)
            except AnnotationCategory.DoesNotExist:
                create_args = {"name": data.get("name"), "owner": request.user}
                if "color" in data:
                    create_args["color"] = data.get("color")
                if "video_id" in data:
                    try:
                        video_db = Video.objects.get(id=data.get("video_id"))
                    except Video.DoesNotExist:
                        return JsonResponse({"status": "error", "type": "not_exist"})
                    create_args["video"] = video_db

                annotation_category_db = AnnotationCategory.objects.create(**create_args)
            return JsonResponse({"status": "ok", "entry": annotation_category_db.to_dict()})
        except Exception:
            logger.exception('Failed to create AnnotationCategory')
            return JsonResponse({"status": "error"})


class AnnoatationCategoryList(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            query_args = {}

            query_args["owner"] = request.user

            if "video_id" in request.GET:
                query_args["video__id"] = request.GET.get("video_id")

            query_results = AnnotationCategory.objects.filter(**query_args)

            entries = []
            for annotation_category in query_results:
                entries.append(annotation_category.to_dict())
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception('Failed to list AnnotationCategory')
            return JsonResponse({"status": "error"})
