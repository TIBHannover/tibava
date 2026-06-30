import uuid
import logging
import traceback


from django.views import View
from django.http import HttpResponse, JsonResponse
from django.conf import settings

# from django.core.exceptions import BadRequest

from backend.models import Video, PluginRun
from backend.plugin_manager import PluginManager


logger = logging.getLogger(__name__)


class PluginList(View):
    def get(self, request):
        plugin_manager = PluginManager()
        try:
            entries = [{"name": x} for x in plugin_manager.plugins()]

            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception("Failed to list plugins")
            return JsonResponse({"status": "error"})
