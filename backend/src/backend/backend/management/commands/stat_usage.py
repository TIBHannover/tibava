from django.core.management.base import BaseCommand, CommandError
from backend.models import (
    Video,
    TimelineSegment,
    Timeline,
    TibavaUser,
    AnnotationCategory,
    Annotation,
    TimelineSegmentAnnotation,
    PluginRun,
    PluginRunResult,
    ClusterTimelineItem,
    ClusterItem,
    VideoAnalysisState,
)
from django.db import transaction


class Command(BaseCommand):
    help = "Closes the specified poll for voting"

    def add_arguments(self, parser):
        parser.add_argument("--blacklist-usernames", nargs="+", type=str)

    def handle(self, *args, **options):
        blacklist_usernames = options["blacklist_usernames"]
        if not blacklist_usernames:
            blacklist_usernames = []

        user_count = {"all": 0, "videos_5": 0, "videos_10": 0, "videos_50": 0}
        video_count = {"all": 0, "videos_10": 0, "videos_60": 0, "duration": 0.0}
        plugin_count = {"all": 0}
        plugin_video_count = {
            "videos_plugin_5": 0,
            "videos_plugin_10": 0,
            "videos_plugin_20": 0,
        }

        for user_db in TibavaUser.objects.exclude(username__in=blacklist_usernames):
            user_count["all"] += 1

            num_videos = len(Video.objects.filter(owner=user_db))
            if num_videos >= 5:
                user_count["videos_5"] += 1
            if num_videos >= 10:
                user_count["videos_10"] += 1
            if num_videos >= 50:
                user_count["videos_50"] += 1

            for video_db in Video.objects.filter(owner=user_db):
                video_count["all"] += 1
                if video_db.duration / 60 >= 10:
                    video_count["videos_10"] += 1
                if video_db.duration / 60 >= 60:
                    video_count["videos_60"] += 1
                video_count["duration"] += video_db.duration / 60

                num_plugins = len(PluginRun.objects.filter(video=video_db))
                plugin_count["all"] += num_plugins

                if num_plugins >= 5:
                    plugin_video_count["videos_plugin_5"] += 1
                if num_plugins >= 10:
                    plugin_video_count["videos_plugin_10"] += 1
                if num_plugins >= 20:
                    plugin_video_count["videos_plugin_20"] += 1

        self.stdout.write(self.style.SUCCESS(f"User stats: {user_count}"))
        self.stdout.write(self.style.SUCCESS(f"Video stats: {video_count}"))
        self.stdout.write(self.style.SUCCESS(f"Plugin stats: {plugin_count}"))
        self.stdout.write(
            self.style.SUCCESS(f"Plugin Video stats: {plugin_video_count}")
        )
