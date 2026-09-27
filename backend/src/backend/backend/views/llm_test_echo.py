# DEBUG-only dev/testing utility (see README.md, "Testing LLM/API-based
# plugins without a real endpoint"). Point a plugin's outbound LLM/API-URL
# setting (e.g. GEOLOCATION_LLM_API_URL) at
# http://backend:8000/llm/test-echo/<plugin_name>/ to log the outbound
# request instead of hitting a real external API, and to get back a fixed
# response so the rest of the pipeline (parsing, DB writes) can be exercised.
# Returns 404 unless DEBUG=true, so it's kept in the codebase as a reusable
# tool rather than deleted after each use.
#
# To watch the log lines this endpoint writes while testing:
#   docker-compose logs -f backend celery

import json
import logging

from django.conf import settings
from django.http import HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from backend.utils.llm_client import (
    MockGeolocationLLMClient,
    mask_header,
    summarize_for_log,
)

logger = logging.getLogger(__name__)


def _random_geolocation_candidates():
    return MockGeolocationLLMClient().locate([], "")


# Canned responses per plugin name, so a plugin whose task expects a
# particular shape (e.g. geolocation's candidate list) can exercise its
# real parsing/DB-write code against a valid reply. A value may be a plain
# list (returned as-is) or a callable (invoked per request, e.g. to
# randomize). Plugins without an entry here get an empty list back.
FIXTURES = {
    "geolocation": _random_geolocation_candidates,
}


@csrf_exempt
def llm_test_echo(request, plugin_name: str):
    if not settings.DEBUG:
        return HttpResponseNotFound()

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = f"<{len(request.body)} bytes, not valid JSON>"

    logger.info(
        "llm_test_echo: plugin_name=%s method=%s path=%s content_type=%s "
        "content_length=%s headers=%s body=%s",
        plugin_name,
        request.method,
        request.path,
        request.content_type,
        request.headers.get("Content-Length"),
        {k: mask_header(k, v) for k, v in request.headers.items()},
        summarize_for_log(body),
    )

    fixture = FIXTURES.get(plugin_name, [])
    return JsonResponse(fixture() if callable(fixture) else fixture, safe=False)
