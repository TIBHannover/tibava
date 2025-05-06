import os
import json
from django.core.management.base import BaseCommand, CommandError
from backend.models import Video
import pathlib
import imageio
import shutil
import uuid
from django.contrib import auth
from django.conf import settings


from backend.plugin_manager import PluginManager


class Command(BaseCommand):
    help = "Closes the specified poll for voting"

    def add_arguments(self, parser):
        parser.add_argument("--user", type=str)
        parser.add_argument("--video", type=str)
        parser.add_argument("--name", default="dir", choices=["dir", "filename"], type=str)

    def handle(self, *args, **options):
        try:
            user = auth.get_user_model().objects.get(id=options["user"])
        except auth.get_user_model().DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f"User does not exist"))
            return
        print(os.listdir(options["video"]))
        if os.path.isdir(options["video"]):
            for root, dirs, files in os.walk(options["video"]):
                for f in files:
                    file_path = os.path.join(root, f)

                    path = pathlib.Path(file_path)

                    if options["name"] == "dir":
                        video_name = path.parent.name
                    elif options["name"] == "filename":
                        video_name = path.stem

                    reader = imageio.get_reader(file_path)
                    fps = reader.get_meta_data()["fps"]
                    duration = reader.get_meta_data()["duration"]
                    size = reader.get_meta_data()["size"]

                    ext = path.suffix

                    video_id_uuid = uuid.uuid4()
                    video_id = video_id_uuid.hex

                    output_dir = os.path.join(settings.MEDIA_ROOT)
                    shutil.copyfile(file_path, os.path.join(output_dir, f"{video_id}{ext}"))

                    video_db, created = Video.objects.get_or_create(
                        name=video_name,
                        id=video_id_uuid,
                        ext=ext,
                        fps=fps,
                        duration=duration,
                        width=size[0],
                        height=size[1],
                        owner=user,
                    )

                    print(video_id_uuid.hex)

        self.stdout.write(self.style.SUCCESS(f"Videos added"))
        # else:
        #     options["video"]
