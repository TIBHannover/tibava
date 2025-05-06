import json
import logging
import traceback


from django.views import View
from django.http import JsonResponse
from numpy import isin

from backend.models import AnnotationShortcut, Shortcut, Video, Annotation

logger = logging.getLogger(__name__)


# from django.core.exceptions import BadRequest
class AnnotationShortcutCreate(View):
    def post(self, request):

        return JsonResponse({"status": "error"})

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
                shortcut_db = AnnotationShortcut.objects.get(**query_args)
            except AnnotationShortcut.DoesNotExist:
                create_args = {"key": data.get("key"), "owner": request.user}
                if "video_id" in data:
                    try:
                        video_db = Video.objects.get(id=data.get("video_id"))
                    except Video.DoesNotExist:
                        return JsonResponse({"status": "error", "type": "not_exist"})
                    create_args["video"] = video_db

                shortcut_db = AnnotationShortcut.objects.create(**create_args)
            return JsonResponse({"status": "ok", "entry": shortcut_db.to_dict()})
        except Exception as e:
            logger.error(traceback.format_exc())
            return JsonResponse({"status": "error"})


# from django.core.exceptions import BadRequest
class AnnotationShortcutUpdate(View):
    def delete_shortcut(self, annotation_shortcut, user, annotation, video=None):
        AnnotationShortcut.objects.filter(annotation=annotation).delete()

    def update_shortcut(self, annotation_shortcut, user, annotation, video=None):
        keys = annotation_shortcut.get("keys")
        id = annotation_shortcut.get("id")
        keys_string = Shortcut.generate_keys_string(keys)

        try:
            shortcut_db = Shortcut.objects.get(keys_string=keys_string, video=video, owner=user, type="annotation")
        except Shortcut.DoesNotExist:
            shortcut_db = Shortcut.objects.create(
                keys=keys, keys_string=keys_string, video=video, owner=user, type="annotation"
            )

        try:
            annotation_shortcut_db = AnnotationShortcut.objects.get(annotation=annotation)

            annotation_shortcut_db.shortcut = shortcut_db
            annotation_shortcut_db.save()
        except AnnotationShortcut.DoesNotExist:
            annotation_shortcut_db = AnnotationShortcut.objects.create(annotation=annotation, shortcut=shortcut_db)

        return {"annotation_shortcut": annotation_shortcut_db, "shortcut": shortcut_db}

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

            if "annotation_shortcuts" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})

            annotation_shortcuts = data.get("annotation_shortcuts")
            if not isinstance(annotation_shortcuts, list):
                return JsonResponse({"status": "error", "type": "wrong_type"})

            video_db = None
            if "video_id" in data:
                try:
                    video_db = Video.objects.get(id=data.get("video_id"))
                except Video.DoesNotExist:
                    return JsonResponse({"status": "error", "type": "not_exist"})

            results = []
            for annotation_shortcut in annotation_shortcuts:
                if "id" not in annotation_shortcut:
                    continue
                annotation_db = None
                try:
                    annotation_db = Annotation.objects.get(id=annotation_shortcut.get("id"))
                except Annotation.DoesNotExist:
                    continue

                if "keys" not in annotation_shortcut:
                    self.delete_shortcut(
                        annotation_shortcut, user=request.user, annotation=annotation_db, video=video_db
                    )
                else:
                    keys = annotation_shortcut.get("keys")
                    if not isinstance(keys, list) or len(keys) == 0:
                        self.delete_shortcut(
                            annotation_shortcut, user=request.user, annotation=annotation_db, video=video_db
                        )
                    else:
                        shortcuts = self.update_shortcut(
                            annotation_shortcut, user=request.user, annotation=annotation_db, video=video_db
                        )
                        results.append(shortcuts)

            return JsonResponse(
                {
                    "status": "ok",
                    "annotation_shortcuts": [x["annotation_shortcut"].to_dict() for x in results],
                    "shortcuts": [x["shortcut"].to_dict() for x in results],
                }
            )

        except Exception:
            logger.exception('Failed to update AnnotationShortcut')
            return JsonResponse({"status": "error"})


class AnnotationShortcutList(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            query_args = {}

            if "video_id" in request.GET:
                query_args["shortcut__video__id"] = request.GET.get("video_id")

            query_results = AnnotationShortcut.objects.filter(**query_args)

            entries = []
            for shortcut in query_results:
                entries.append(shortcut.to_dict())
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception('Failed to list annotation shortcuts')
            return JsonResponse({"status": "error"})
