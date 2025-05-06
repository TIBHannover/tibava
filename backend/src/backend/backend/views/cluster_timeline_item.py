import json
import logging
import uuid

from django.views import View
from django.http import JsonResponse

from backend.models import ClusterTimelineItem, Video, PluginRun


logger = logging.getLogger(__name__)


class ClusterTimelineItemCreate(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error", "type": "user_auth"})
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            data = json.loads(body)

            video = Video.objects.get(id=data["video_id"])
            plugin_run = PluginRun.objects.get(id=uuid.UUID(data['plugin_run']))
            cluster_timeline_item = ClusterTimelineItem.objects.create(
                cluster_id=uuid.uuid4(),
                name=data["name"],
                video=video,
                plugin_run=plugin_run,
                type=data['type']
            )

            return JsonResponse({"status": "ok", "entry": cluster_timeline_item.to_dict()})
        except Exception:
            logger.exception('Failed to create cluster timeline item')
            return JsonResponse({"status": "error", "type" : "general"})
        
class ClusterTimelineItemDelete(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error", "type": "user_auth"})
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error", "type": "data_load"})
            count, _ = ClusterTimelineItem.objects.filter(id=data.get("id")).delete()
            if count:
                return JsonResponse({"status": "ok"})
            return JsonResponse({"status": "error", "type": "delete_op"})
        except Exception:
            logger.exception('Failed to delete cluster timeline item')
            return JsonResponse({"status": "error"})


class ClusterTimelineItemRename(View):
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
                return JsonResponse({"status": "error", "type": "dataload"})

            if "cti_id" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if "name" not in data:
                return JsonResponse({"status": "error", "type": "missing_values"})
            if not isinstance(data.get("name"), str):
                return JsonResponse({"status": "error", "type": "wrong_request_body"})

            try:
                cti = ClusterTimelineItem.objects.get(id=data.get("cti_id"))
            except ClusterTimelineItem.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            cti.name = data.get("name")
            cti.save()
            return JsonResponse({"status": "ok", "entry": cti.to_dict()})
        except Exception:
            logger.exception('Failed to rename cluster timeline item')
            return JsonResponse({"status": "error"})

class ClusterTimelineItemFetch(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error_user_auth"})
            
            video_id = uuid.UUID(hex=request.GET.get('video_id'))
            entries = [
                cti.to_dict()
                for cti in ClusterTimelineItem.objects.filter(video_id=video_id)
            ]

            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception('Failed to fetch cluster timeline item')
            return JsonResponse({"status": "error"})


class ClusterTimelineItemMerge(View):
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
                return JsonResponse({"status": "error", "type": "dataload"})
            
            if 'from_id' not in data or 'to_id' not in data:
                return JsonResponse({'status': 'error', 'type': 'Params missing'})

            from_cluster = ClusterTimelineItem.objects.get(id=data['from_id'])
            ClusterTimelineItem.objects.get(id=data['to_id'])

            from_cluster.items.update(cluster_timeline_item_id=data['to_id'])
            from_cluster.delete()
            return JsonResponse({'status': 'ok'})

        except:
            logger.exception('Failed to merge clusters')
