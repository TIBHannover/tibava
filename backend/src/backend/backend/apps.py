import logging

from django.apps import AppConfig
from django.db.models import Q
from django.db import connection


logger = logging.getLogger(__name__)


class BackendConfig(AppConfig):
    name = "backend"

    def ready(self):
        if 'backend_pluginrun' not in connection.introspection.table_names():
            return
        # import here otherwise django complains
        from tibava.celery import app
        from backend.models import PluginRun

        # set unfinished tasks to ERROR on startup
        inspect = app.control.inspect()

        scheduled = inspect.scheduled()
        active = inspect.active()
        reserved = inspect.reserved()

        # inspect can return None or dict
        if scheduled is None or active is None or reserved is None:
            return

        celery_runs = [
            run['args'][0]['plugin_run']
            for category in (list(scheduled.values()) +
                             list(active.values()) +
                             list(reserved.values()))
            for run in category
        ]

        open_runs = PluginRun.objects.exclude(Q(status=PluginRun.STATUS_DONE)|
                                              Q(status=PluginRun.STATUS_ERROR)|
                                              Q(id__in=celery_runs))
        if len(open_runs) > 0:
            logger.warning(
                f'Setting the status of {len(open_runs)} non-running PluginRuns to UNKNOWN'
            )
            open_runs.update(status=PluginRun.STATUS_UNKNOWN)
