import os
import shutil
import sys
import json
import uuid
import logging
import traceback
import tempfile
import logging
from pathlib import Path

from urllib.parse import urlparse
import imageio
from backend.plugin_manager import PluginManager

from backend.utils import (
    download_url,
    download_file,
    media_url_to_video,
    media_path_to_video,
    media_dir_to_video,
)

from django.views import View
from django.http import JsonResponse
from django.conf import settings

# from django.core.exceptions import BadRequest

from backend.models import Video


logger = logging.getLogger(__name__)


class VideoUpload(View):
    def submit_analyse(self, plugins, **kwargs):
        plugin_manager = PluginManager()
        for plugin in plugins:
            plugin_manager(plugin, **kwargs)

    def post(self, request):
        try:
            if not request.user.is_authenticated:
                logger.error("VideoUpload::not_authenticated")
                return JsonResponse(
                    {"status": "error", "type": "not_authenticated"}, status=500
                )

            if request.method != "POST":
                logger.error("VideoUpload::wrong_method")
                return JsonResponse(
                    {"status": "error", "type": "database_error"}, status=500
                )
            video_id_uuid = uuid.uuid4()
            video_id = video_id_uuid.hex
            if "file" in request.FILES:
                output_dir = media_dir_to_video(video_id)

                download_result = download_file(
                    output_dir=output_dir,
                    output_name=video_id,
                    file=request.FILES["file"],
                    max_size=request.user.max_video_size,
                    extensions=(".mkv", ".mp4", ".ogv"),
                )

                if download_result["status"] != "ok":
                    logger.error("VideoUpload::failed")
                    return JsonResponse(download_result, status=500)

                path = Path(request.FILES["file"].name)
                ext = "".join(path.suffixes)

                reader = imageio.get_reader(download_result["path"])
                fps = reader.get_meta_data()["fps"]
                duration = reader.get_meta_data()["duration"]
                size = reader.get_meta_data()["size"]
                meta = {
                    "name": request.POST.get("title"),
                    "width": size[0],
                    "height": size[1],
                    "ext": ext,
                    "fps": fps,
                    "duration": duration,
                }
                video_db, created = Video.objects.get_or_create(
                    name=meta["name"],
                    id=video_id_uuid,
                    file=video_id_uuid,
                    ext=meta["ext"],
                    fps=meta["fps"],
                    duration=meta["duration"],
                    width=meta["width"],
                    height=meta["height"],
                    owner=request.user,
                )
                if not created:
                    logger.error("VideoUpload::database_create_failed")
                    return JsonResponse(
                        {"status": "error", "type": "database_error"}, status=500
                    )

                analyers = request.POST.get("analyser").split(",")
                self.submit_analyse(
                    plugins=["thumbnail"] + analyers, video=video_db, user=request.user
                )

                video_id_hex = video_db.id.hex if not video_db.file.hex else video_db.id.hex
                return JsonResponse(
                    {
                        "status": "ok",
                        "entries": [
                            {
                                "id": video_id,
                                **video_db.to_dict(),
                                "url": media_url_to_video(video_id_hex, meta["ext"]),
                            }
                        ],
                    }
                )

            return JsonResponse({"status": "error"}, status=500)

        except Exception:
            logger.exception("Video upload by user failed")
            return JsonResponse({"status": "error"}, status=500)


class VideoList(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"}, status=500)
            entries = []
            for video in Video.objects.filter(owner=request.user):
                entries.append(video.to_dict())
            return JsonResponse({"status": "ok", "entries": entries})
        except Exception as e:
            logger.exception("Error listing videos")
            return JsonResponse({"status": "error"}, status=500)


class VideoGet(View):
    def get(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"}, status=500)

            entries = []
            for video in Video.objects.filter(id=request.GET.get("id"), owner=request.user):
                video_id_hex = video.id.hex if not video.file else video.file.hex
                entries.append(
                    {
                        **video.to_dict(),
                        "url": media_url_to_video(video_id_hex, video.ext),
                    }
                )
            if len(entries) != 1:
                return JsonResponse({"status": "error"}, status=500)
            return JsonResponse({"status": "ok", "entry": entries[0]})
        except Exception:
            logger.exception("Failed to get video")
            return JsonResponse({"status": "error"}, status=500)


class VideoRename(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"}, status=500)
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error"}, status=500)

            if "id" not in data:
                return JsonResponse(
                    {"status": "error", "type": "missing_values"}, status=500
                )
            if "name" not in data:
                return JsonResponse(
                    {"status": "error", "type": "missing_values"}, status=500
                )
            if not isinstance(data.get("name"), str):
                return JsonResponse(
                    {"status": "error", "type": "wrong_request_body"}, status=500
                )

            try:
                video_db = Video.objects.get(id=data.get("id"))
            except Video.DoesNotExist:
                return JsonResponse(
                    {"status": "error", "type": "not_exist"}, status=500
                )

            video_db.name = data.get("name")
            video_db.save()
            return JsonResponse({"status": "ok", "entry": video_db.to_dict()})
        except Exception:
            logger.exception("Failed to rename video")
            return JsonResponse({"status": "error"}, status=500)


class VideoDelete(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"}, status=500)
            try:
                body = request.body.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                body = request.body

            try:
                data = json.loads(body)
            except Exception as e:
                return JsonResponse({"status": "error"}, status=500)
            count, _ = Video.objects.filter(
                id=data.get("id"), owner=request.user
            ).delete()
            if count:
                return JsonResponse({"status": "ok"})
            return JsonResponse({"status": "error"}, status=500)
        except Exception:
            logger.exception("Failed to delete video")
            return JsonResponse({"status": "error"}, status=500)
