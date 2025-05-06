from django.http import JsonResponse
from django.contrib import auth
from django.views.decorators.http import require_http_methods

from django.views.decorators.csrf import ensure_csrf_cookie
import logging
import json
import traceback

from django.views.decorators.csrf import csrf_protect
from django.views import View


logger = logging.getLogger(__name__)


# def get_csrf_token(request):
#     token = get_token(request)
#     return JsonResponse({"token": token})


@ensure_csrf_cookie
def get_csrf_token(request):
    # token = get_token(request)
    return JsonResponse({"status": "ok"})


class UserGet(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "error": {"type": "not_authenticated"}})

        try:
            user = request.user
            return JsonResponse(
                {
                    "status": "ok",
                    "data": {
                        "username": user.get_username(),
                        "email": user.email,
                        "date": user.date_joined,
                        "allowance": user.allowance,
                        "max_video_size": user.max_video_size,
                    },
                }
            )
        except Exception:
            logger.exception('Failed to get user info')
            return JsonResponse({"status": "error"})


@require_http_methods(["POST"])
def login(request):
    try:
        body = request.body.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        body = request.body

    try:
        data = json.loads(body)
    except Exception as e:
        logger.exception('Could not load JSON for login')
        return JsonResponse({"status": "error"})

    if "name" not in data["params"]:
        logger.warning('Name not supplied for login')
        return JsonResponse({"status": "error", "message": "Name missing"})

    if "password" not in data["params"]:
        logger.warning('Password not supplied for login')
        return JsonResponse({"status": "error", "message": "Password missing"})

    username = data["params"]["name"]
    password = data["params"]["password"]

    if username == "" or password == "":
        return JsonResponse({"status": "error", "message": "Value empty"})

    user = auth.authenticate(username=username, password=password)
    if user is not None:
        auth.login(request, user)
        return JsonResponse(
            {
                "status": "ok",
                "data": {
                    "username": user.get_username(),
                    "email": user.email,
                    "date": user.date_joined,
                    "allowance": user.allowance,
                    "max_video_size": user.max_video_size,
                },
            }
        )

    return JsonResponse({"status": "error", "message": "Invalid login credentials"})


@require_http_methods(["POST"])
def register(request):
    try:
        body = request.body.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        body = request.body

    try:
        data = json.loads(body)
    except Exception as e:
        logger.exception('Could not load JSON for register')
        return JsonResponse({"status": "error"})

    if "name" not in data["params"]:
        logger.warning('Name not supplied for registration')
        return JsonResponse({"status": "error", "message": "Name missing"})

    if "password" not in data["params"]:
        logger.warning('Password not supplied for registration')
        return JsonResponse({"status": "error", "message": "Password missing"})

    if "email" not in data["params"]:
        logger.warning('EMail not supplied for registration')
        return JsonResponse({"status": "error", "message": "E-Mail missing"})

    username = data["params"]["name"]
    password = data["params"]["password"]
    email = data["params"]["email"]

    if username == "" or password == "" or email == "":
        logger.warning("An input is missing for registration.")
        return JsonResponse({"status": "error", "message": "Input empty"})

    if auth.get_user_model().objects.filter(username=username).count() > 0:
        logger.warning("User already exists. Abort.")
        return JsonResponse({"status": "error", "message": "User already exists"})

    # TODO Add EMail register here
    user = auth.get_user_model().objects.create_user(username, email, password)
    user = auth.authenticate(username=username, password=password)
    logger.info('New user registered')

    if user is not None:
        auth.login(request, user)
        return JsonResponse({"status": "ok"})

    return JsonResponse({"status": "error"})


@require_http_methods(["POST"])
def logout(request):
    auth.logout(request)
    return JsonResponse({"status": "ok"})
