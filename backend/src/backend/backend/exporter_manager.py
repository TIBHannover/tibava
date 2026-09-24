import json
import logging
import os
import sys
import traceback
from typing import List, Optional

from celery import shared_task
from django.conf import settings
from tibava_data import DataManager

from backend.models import ExporterRun, Video

logger = logging.getLogger(__name__)


class Exporter:
    pass


class ExporterManager:
    _plugins = {}
    _parser = {}

    def __init__(self):
        self._exporters = {}

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

    def plugins(self):
        plugins = self._plugins
        if settings.PLUGIN_WHITELIST is not None:
            plugins = {
                x: y for x, y in plugins.items() if x in settings.PLUGIN_WHITELIST
            }

        if settings.PLUGIN_BLACKLIST is not None:
            plugins = {
                x: y for x, y in plugins.items() if x not in settings.PLUGIN_BLACKLIST
            }
        return plugins

    def __call__(
        self,
        plugin: str,
        video: Video,
        parameters: Optional[List] = None,
        # run_async: bool = True,
        # dry_run: bool = False,
        **kwargs,
    ):
        if parameters is None:
            parameters = []

        if plugin not in self.plugins():
            logging.error("Unknown exporter plugin")
            return {"status": False}

        if plugin in self._parser:
            parameters = self._parser[plugin]()(parameters)
        else:
            parameters = {}

        result = {"status": True}
        exporter_run = ExporterRun.objects.create(
            video=video, type=plugin, status=ExporterRun.STATUS_QUEUED
        )

        video_export.apply_async(
            (
                {
                    "plugin": plugin,
                    "parameters": parameters,
                    "video": video.id,
                    "exporter_run": exporter_run.id if exporter_run else None,
                    "kwargs": kwargs,
                },
            )
        )

        return result


import traceback


@shared_task(bind=True, max_retries=None)
def video_export(self, args):
    print(args, flush=True)
    plugin = args.get("plugin")
    parameters = args.get("parameters")
    video = args.get("video")
    exporter_run = args.get("exporter_run")
    kwargs = args.get("kwargs")

    video_db = Video.objects.get(id=video)

    exporter_run_db = ExporterRun.objects.get(id=exporter_run)
    # this job is already started in another jobqueue https://github.com/celery/celery/issues/4400
    if exporter_run_db.in_scheduler:
        logger.warning("Job was rescheduled and will be canceled")
        return
    exporter_run_db.in_scheduler = True
    exporter_run_db.save()

    exporter_manager = ExporterManager()

    print("TEST", flush=True)

    try:
        exporter_result = exporter_manager._plugins[plugin]()(
            parameters,
            video=video_db,
            exporter_run=exporter_run_db,
            **kwargs,
        )

    except Exception as e:
        # raise e
        logging.error(f"[Analyser] {repr(e)}")
        exc_type, exc_value, exc_traceback = sys.exc_info()

        traceback.print_exception(
            exc_type,
            exc_value,
            exc_traceback,
            limit=2,
            file=sys.stdout,
        )


@shared_task(bind=True, max_retries=None)
def video_import(self, args):
    pass
