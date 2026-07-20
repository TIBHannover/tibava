from django.db import connection
from django.core.cache import cache
from django.http import JsonResponse


def liveness(request):
    """Simple check to verify the application process is running."""
    return JsonResponse({"status": "ok"}, status=200)


def readiness(request):
    """Deep check to verify core services (Database, Cache) are reachable."""
    status = {"status": "ok", "checks": {}}
    http_status = 200

    # 1. Test Database Connectivity
    try:
        connection.ensure_connection()
        status["checks"]["database"] = "ok"
    except Exception as e:
        status["checks"]["database"] = f"unreachable: {str(e)}"
        status["status"] = "error"
        http_status = 503

    # 2. Test Cache (e.g., Redis / Memcached)
    try:
        cache.set("_healthcheck", "ok", timeout=5)
        if cache.get("_healthcheck") == "ok":
            status["checks"]["cache"] = "ok"
        else:
            raise Exception("Cache read/write mismatch")
    except Exception as e:
        status["checks"]["cache"] = f"unreachable: {str(e)}"
        status["status"] = "error"
        http_status = 503

    return JsonResponse(status, status=http_status)
