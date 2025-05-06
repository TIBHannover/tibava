import logging
import traceback
import sys
import os
import json
from typing import List

from celery import shared_task
from backend.models import PluginRun, Video, TibavaUser, PluginRunResult
from data import DataManager

from django.conf import settings

# class PluginRunResults(datacla):


logger = logging.getLogger(__name__)


class PluginManager:
    _plugins = {}
    _parser = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def export_parser(cls, name):
        def export_helper(parser):
            cls._parser[name] = parser
            return parser

        return export_helper

    @classmethod
    def export_plugin(cls, name):
        def export_helper(plugin):
            cls._plugins[name] = plugin
            return plugin

        return export_helper

    def __contains__(self, plugin):
        return plugin in self._plugins

    def __call__(
        self,
        plugin: str,
        video: Video,
        user: TibavaUser,
        parameters: List = None,
        run_async: bool = True,
        dry_run: bool = False,
        **kwargs,
    ):
        if parameters is None:
            parameters = []

        if plugin not in self._plugins:
            print("Unknown Plugin")
            return {"status": False}

        logger.info(
            f'User "{user.username}" has started plugin "{plugin}" with parameters {parameters}'
        )

        if plugin in self._parser:
            parameters = self._parser[plugin]()(parameters)
        else:
            parameters = {}

        result = {"status": True}
        plugin_run = None
        if not dry_run:
            plugin_run = PluginRun.objects.create(
                video=video, type=plugin, status=PluginRun.STATUS_QUEUED
            )
        if run_async:
            run_plugin.apply_async(
                (
                    {
                        "plugin": plugin,
                        "parameters": parameters,
                        "video": video.id,
                        "user": user.id,
                        "plugin_run": plugin_run.id if plugin_run else None,
                        "dry_run": dry_run,
                        "kwargs": kwargs,
                    },
                )
            )
        else:
            try:
                plugin_result = self._plugins[plugin]()(
                    parameters,
                    user=user,
                    video=video,
                    plugin_run=plugin_run,
                    dry_run=dry_run,
                    **kwargs,
                )
                if plugin_run is not None:
                    plugin_run.progress = 1.0
                    plugin_run.status = PluginRun.STATUS_DONE
                    plugin_run.save()

                # Create cache files for all plugin run results.
                manager = DataManager("/predictions/")

                generate_plugin_run_result_cache(
                    manager, plugin_result.get("plugin_run_results", [])
                )
                if plugin_result:
                    result["result"] = plugin_result

            except Exception:
                logger.exception(f"Failed to run plugin {plugin_run.type}")

                if plugin_run is not None:
                    plugin_run.status = PluginRun.STATUS_ERROR
                    plugin_run.save()
                result["status"] = False
                return result
        return result

    def get_results(self, analyse):
        if not hasattr(analyse, "type"):
            return None
        if analyse.type not in self._plugins:
            return None
        analyser = self._plugins[analyse.type]()
        if not hasattr(analyser, "get_results"):
            return {}
        return analyser.get_results(analyse)


def generate_plugin_run_result_cache(
    data_manager, plugin_run_result: List[str]
) -> None:
    for plugin_run_result_id in plugin_run_result:
        x = PluginRunResult.objects.get(id=plugin_run_result_id)
        # print("B", flush=True)
        cache_path = os.path.join(settings.DATA_CACHE_ROOT, f"{x.id}.json")
        # print("C", flush=True)
        # print(cache_path, flush=True)
        cached = False
        try:
            if os.path.exists(cache_path):
                with open(cache_path, "r") as f:
                    cached = True
        except Exception:
            logger.exception("Cache reading failed")
        if cached:
            continue
        # print(f"x {x}")
        # TODO fix me
        data = data_manager.load(x.data_id)
        if data is None:
            continue
        # print(data)
        with data:
            result_dict = {**x.to_dict(), "data": data.to_dict()}
            try:
                with open(cache_path, "w") as f:
                    json.dump(result_dict, f)
                    logger.debug(f"Writin result {x.id} to cache")
            except Exception:
                logger.exception("Cache couldn't write")


@shared_task(bind=True)
def run_plugin(self, args):
    plugin = args.get("plugin")
    parameters = args.get("parameters")
    video = args.get("video")
    user = args.get("user")
    plugin_run = args.get("plugin_run")
    dry_run = args.get("dry_run")
    kwargs = args.get("kwargs")

    video_db = Video.objects.get(id=video)
    user_db = TibavaUser.objects.get(id=user)
    plugin_run_db = None
    if not dry_run:
        plugin_run_db = PluginRun.objects.get(id=plugin_run)
        # this job is already started in another jobqueue https://github.com/celery/celery/issues/4400
        if plugin_run_db.in_scheduler:
            logger.warning("Job was rescheduled and will be canceled")
            return
        plugin_run_db.in_scheduler = True
        plugin_run_db.save()

    plugin_manager = PluginManager()
    try:
        plugin_result = plugin_manager._plugins[plugin]()(
            parameters,
            user=user_db,
            video=video_db,
            plugin_run=plugin_run_db,
            dry_run=dry_run,
            **kwargs,
        )

        # Create cache files for all plugin run results.
        manager = DataManager("/predictions/")

        generate_plugin_run_result_cache(
            manager, plugin_result.get("plugin_run_results", [])
        )

        if plugin_run_db is not None:
            plugin_run_db.progress = 1.0
            plugin_run_db.status = PluginRun.STATUS_DONE
            plugin_run_db.save()

        return

    except Exception:
        logger.exception(f"Plugin run failed for {plugin}")

    if plugin_run_db is not None:
        plugin_run_db.status = PluginRun.STATUS_ERROR
        plugin_run_db.save()
