import json
import logging
import traceback


from django.views import View
from django.http import JsonResponse
# from django.core.exceptions import BadRequest

from backend.models import Shortcut, Video


logger = logging.getLogger(__name__)


class ShortcutCreate(View):
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

            if "key" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            try:
                query_args = {"key": data.get("key"), "video_id": request.user}
                if "video_id" in data:
                    query_args["video__id"] = data.get("video_id")
                shortcut_db = Shortcut.objects.get(**query_args)
            except Shortcut.DoesNotExist:
                create_args = {"key": data.get("key"), "owner": request.user}
                if "video_id" in data:
                    try:
                        video_db = Video.objects.get(id=data.get("video_id"))
                    except Video.DoesNotExist:
                        return JsonResponse({"status": "error", "type": "not_exist"})
                    create_args["video"] = video_db

                shortcut_db = Shortcut.objects.create(**create_args)
            return JsonResponse({"status": "ok", "entry": shortcut_db.to_dict()})
        except Exception:
            logger.exception("Failed to create shortcut")
            return JsonResponse({"status": "error"})


class ShortcutList(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            query_args = {}

            query_args["owner"] = request.user

            if "video_id" in request.GET:
                query_args["video__id"] = request.GET.get("video_id")

            query_results = Shortcut.objects.filter(**query_args)

            entries = []
            for shortcut in query_results:
                entries.append(shortcut.to_dict())
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception("Failed to list shortcuts")
            return JsonResponse({"status": "error"})
