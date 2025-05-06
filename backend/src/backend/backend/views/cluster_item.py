import logging
import json
import time

from django.views import View
from django.http import JsonResponse

from backend.models import ClusterItem


logger = logging.getLogger(__name__)


class ClusterItemFetch(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error_user_auth"})

            entries = [
                item.to_dict()
                for item in ClusterItem.objects.filter(video_id=request.GET.get('video_id'))
            ]

            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception('Failed to fetch cluster items')
            return JsonResponse({"status": "error"})


class ClusterItemDelete(View):
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
            except Exception:
                return JsonResponse({"status": "error"})

            if "item_ids" not in data:
                return JsonResponse(
                    {"status": "error", "type": "missing_values_plugin_item_ref_list"}
                )
            if "cluster_id" not in data:
                return JsonResponse(
                    {"status": "error", "type": "missing_values_cluster_id"}
                )

            item_ids = list(data.get("item_ids"))
            ClusterItem.objects.filter(id__in=item_ids).delete()

            return JsonResponse({"status": "ok", "entries": item_ids})

        except Exception:
            logger.exception('Failed to delete cluster item set')
            return JsonResponse({"status": "error_cluster_item_set_deleted"})


class ClusterItemMove(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error", "type": "user_auth"})
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body
            data = json.loads(body)

            (ClusterItem.objects.filter(id__in=data['item_ids'])
                                .update(cluster_timeline_item=data['new_cluster_id']))
            return JsonResponse({"status": "ok"})
        except Exception:
            logger.exception('Failed to delete cluster timeline item')
            return JsonResponse({"status": "error"})
