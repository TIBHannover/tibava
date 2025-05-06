import os
import time
import json
import logging
import traceback

from django.views import View
from django.http import JsonResponse
from django.conf import settings

# from django.core.exceptions import BadRequest

from backend.models import PluginRunResult, Video, PluginRun
from backend.plugin_manager import PluginManager
from data import DataManager


logger = logging.getLogger(__name__)


class PluginRunResultList(View):
    def get(self, request):
        start_time = time.time()
        if not request.user.is_authenticated:
            logger.error("PluginRunResultList::not_authenticated")
            return JsonResponse({"status": "error"})

        # analyser = Analyser()
        # TODO parameters
        data_manager = DataManager("/predictions/")
        # if True:
        try:
            query_dict = {}

            video_id = request.GET.get("video_id")
            if video_id:
                try:
                    video_db = Video.objects.get(id=video_id)
                except Video.DoesNotExist:
                    return JsonResponse({"status": "error", "type": "not_exist"})

                query_dict["plugin_run__video"] = video_db

            plugin_run_id = request.GET.get("plugin_run_id")
            if plugin_run_id:
                try:
                    plugin_run_db = PluginRun.objects.get(id=plugin_run_id)
                except PluginRun.DoesNotExist:
                    return JsonResponse({"status": "error", "type": "not_exist"})

                query_dict["plugin_run"] = plugin_run_db

            analyses = PluginRunResult.objects.filter(**query_dict)
            # print("PluginRunResultList")
            # for x in analyses:
            #     print(f"\t {x.id.hex}")

            add_results = request.GET.get("add_results", True)
            if add_results:
                # print("A", flush=True)

                entries = []
                for x in analyses:
                    # print("B", flush=True)
                    cache_path = os.path.join(settings.DATA_CACHE_ROOT, f"{x.id}.json")
                    # print("C", flush=True)
                    # print(cache_path, flush=True)
                    cached = False
                    try:
                        if os.path.exists(cache_path):
                            with open(cache_path, "r") as f:
                                entries.append(json.load(f))
                                cached = True
                    except Exception:
                        logger.exception(f"Cache couldn't read {e}")
                    if cached:
                        continue
                    # print(f"x {x}")
                    # TODO fix me
                    data = data_manager.load(x.data_id)
                    if data is None:
                        entries.append({**x.to_dict()})
                        continue
                    # print(data)
                    with data:
                        result_dict = {**x.to_dict(), "data": data.to_dict()}
                        try:
                            with open(cache_path, "w") as f:
                                json.dump(result_dict, f)
                        except Exception:
                            logger.exception(f"Cache couldn't write {e}")

                        entries.append(result_dict)

            else:
                entries = [x.to_dict() for x in analyses]
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception:
            logger.exception("Failed to list plugin run results")
            return JsonResponse({"status": "error"})
