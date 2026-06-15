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
        parser.add_argument("--video-ids", nargs="+", type=str)
        parser.add_argument("--usernames", nargs="+", type=str)

    def handle(self, *args, **options):
        for video_id in options["video_ids"]:
            try:
                video_db = Video.objects.get(pk=video_id)
            except Video.DoesNotExist:
                raise CommandError('Video "%s" does not exist' % video_id)

            for username in options["usernames"]:
                try:
                    user_db = TibavaUser.objects.get(username=username)
                except Video.DoesNotExist:
                    raise CommandError('Video "%s" does not exist' % video_id)

                with transaction.atomic():
                    video_db.pk = None
                    video_db.id = None
                    video_db.owner = user_db
                    video_db.save()

                    plugin_run_result_map = {}
                    plugin_run_map = {}
                    for x in PluginRun.objects.filter(
                        video__id=video_id, status=PluginRun.STATUS_DONE
                    ):
                        original_plugin_run_id = x.id
                        x.pk = None
                        x.id = None
                        x.video = video_db
                        x.save()
                        plugin_run_map[original_plugin_run_id] = x

                        for y in PluginRunResult.objects.filter(
                            plugin_run__id=original_plugin_run_id
                        ):
                            original_plugin_run_result_id = y.id
                            y.pk = None
                            y.id = None
                            y.plugin_run = x
                            y.save()
                            plugin_run_result_map[original_plugin_run_result_id] = y

                    anno_cat_map = {}
                    for x in AnnotationCategory.objects.filter(video__id=video_id):
                        original_anno_cat_id = x.id
                        x.pk = None
                        x.id = None
                        x.video = video_db
                        x.owner = user_db
                        x.save()
                        anno_cat_map[original_anno_cat_id] = x

                    anno_map = {}
                    for x in Annotation.objects.filter(video__id=video_id):
                        original_anno_id = x.id
                        x.pk = None
                        x.id = None
                        if x.category and x.category.id in anno_cat_map:
                            x.category = anno_cat_map[x.category.id]
                        x.video = video_db
                        x.owner = user_db
                        x.save()
                        anno_map[original_anno_id] = x

                    timeline_map = {}
                    for x in Timeline.objects.filter(video__id=video_id):
                        print("TIMELINE")
                        original_timeline_id = x.id
                        x.pk = None
                        x.id = None
                        x.video = video_db
                        timeline_map[original_timeline_id] = x

                        if x.parent and x.parent.id in timeline_map:
                            x.parent = timeline_map[x.parent.id]

                        if (
                            x.plugin_run_result
                            and x.plugin_run_result.id in plugin_run_result_map
                        ):
                            x.plugin_run_result = plugin_run_result_map[
                                x.plugin_run_result.id
                            ]
                        x.save()

                        for y in TimelineSegment.objects.filter(
                            timeline__id=original_timeline_id
                        ):
                            print("TIMELINE_SEGMENT")
                            original_timeline_segment_id = y.id
                            y.pk = None
                            y.id = None
                            y.timeline = x
                            y.save()

                            for z in TimelineSegmentAnnotation.objects.filter(
                                timeline_segment__id=original_timeline_segment_id
                            ):
                                print("TIMELINE_SEGMENT_ANNOTATION")
                                z.pk = None
                                z.id = None
                                z.annotation = anno_map[z.annotation.id]
                                z.timeline_segment = y
                                z.save()

                    for x in ClusterTimelineItem.objects.filter(video__id=video_id):
                        print("ClusterTimelineItem")
                        original_cluster_timeline_item_id = x.id
                        x.pk = None
                        x.id = None
                        x.video = video_db
                        if x.plugin_run and x.plugin_run.id in plugin_run_map:
                            x.plugin_run = plugin_run_map[x.plugin_run.id]
                        x.save()

                        for y in ClusterItem.objects.filter(
                            cluster_timeline_item__id=original_cluster_timeline_item_id
                        ):
                            print("ClusterItem")
                            original_cluster_item_id = y.id
                            y.pk = None
                            y.id = None
                            y.cluster_timeline_item = x
                            if (
                                y.plugin_run_result
                                and y.plugin_run_result.id in plugin_run_result_map
                            ):
                                y.plugin_run_result = plugin_run_result_map[
                                    y.plugin_run_result.id
                                ]
                            y.save()

                self.stdout.write(
                    self.style.SUCCESS('Successfully copied video "%s"' % video_id)
                )
