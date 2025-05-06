from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import shutil
import os
from backend.utils import urls


class Command(BaseCommand):
    help = "Move video files to the new location"

    # def add_arguments(self, parser):
    #     parser.add_argument("video_id", nargs="+", type=int)
    #     parser.add_argument("user_id", nargs="+", type=int)

    def handle(self, *args, **options):
        # print(len("f28e10a4f2b94972bdf42f8c2eb7d9b5"))
        for f in os.listdir(settings.MEDIA_ROOT):
            file_path = os.path.join(settings.MEDIA_ROOT, f)
            if len(os.path.splitext(f)[0]) == 32 and os.path.splitext(file_path)[1].lower() in [".mp4"]:
                print(file_path)
                output_dir = urls.media_dir_to_video(os.path.splitext(f)[0])
                output_path = urls.media_path_to_video(os.path.splitext(f)[0], os.path.splitext(f)[1].lower())
                print(f"{file_path} {output_dir} {output_path}")
                os.makedirs(output_dir, exist_ok=True)
                shutil.move(file_path, output_path)

        # settings.MEDIA_ROOT
        # options["user"]
