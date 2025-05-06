# import os
# import json
# from django.core.management.base import BaseCommand, CommandError
# from backend.models import Video
# import pathlib
# import imageio
# import shutil
# import uuid
# from django.contrib import auth
# from django.conf import settings

# from backend.utils import (
#     download_url,
#     download_file,
#     media_url_to_video,
#     media_path_to_video,
#     media_dir_to_video,
# )

# from backend.plugin_manager import PluginManager
# import json
# from django.core.management.base import BaseCommand, CommandError
# from backend.models import (
#     Video,
#     PluginRun,
#     Timeline,
#     PluginRunResult,
#     TimelineSegment,
#     TimelineSegmentAnnotation,
#     Annotation,
#     AnnotationCategory,
#     TibavaUser,
# )

# from django.contrib import auth
# from django.db import transaction


# class Command(BaseCommand):
#     help = "Closes the specified poll for voting"

#     def add_arguments(self, parser):
#         parser.add_argument("--user_id", type=str)
#         parser.add_argument("--new_username", type=str)

#     def handle(self, *args, **options):
#         with transaction.atomic():
#             try:
#                 user = auth.get_user_model().objects.get(id=options["user_id"])
#             except auth.get_user_model().DoesNotExist as e:
#                 self.stdout.write(self.style.ERROR(f"User does not exist"))
#                 return

#             user.pk = None
#             user.username = options["new_username"]
#             user.save()

#             new_user_db = user

#             old_user_db = auth.get_user_model().objects.get(id=options["user_id"])

#             for video_db in old_user_db.video_set.all():
#                 # print(video.to_dict())

#                 # os.symlink(src, os.path.join(dst, os.path.dirname(src)))

#                 video_id_uuid = uuid.uuid4()
#                 video_id = video_id_uuid.hex
#                 origin_path = media_path_to_video(video_db.id.hex, video_db.ext)

#                 output_dir = media_dir_to_video(video_id)
#                 os.makedirs(output_dir, exist_ok=True)
#                 destination_path = media_path_to_video(video_id, video_db.ext)
#                 # os.symlink(origin_path, destination_path)
#                 shutil.copy(origin_path, destination_path)

#                 video_db.owner = user
#                 video_db.pk = None

#                 video_db.id = video_id_uuid
#                 video_db.save()

#                 for old_plugin_run_db in video_db.pluginrun_set.all():
#                     old_plugin_run_db_id = old_plugin_run_db.id.hex

#                     old_plugin_run_db.pk = None
#                     old_plugin_run_db.video = video_db
#                     old_plugin_run_db.save()


#                     for (
#                         old_plugin_run_result_db
#                     ) in old_plugin_run_db.pluginrunresult_set.all():


#                 for timeline in video.timelines:

#                     plugin_run_db = PluginRun.objects.get(id=result["plugin_run"])
#                     plugin_run_db.pk = None
#                     plugin_run_db.video = video_tgt_db
#                     plugin_run_db.save()

#                     #
#                     # plugin_run_result_map = {}
#                     # for plugin_run_result in result["plugin_run_results"]:

#                     #     plugin_run_result_db = PluginRunResult.objects.get(id = plugin_run_result)
#                     #     old_id = plugin_run_result_db.id.hex
#                     #     plugin_run_result_db.pk = None
#                     #     plugin_run_result_db.plugin_run = plugin_run_db
#                     #     plugin_run_result_db.save()
#                     #     plugin_run_result_lists.append(plugin_run_result_db.id.hex)
#                     #     plugin_run_result_map[old_id] = plugin_run_result_db

#                     plugin_run_result_lists = []
#                     timelines_dict = {}
#                     timelines_list = []
#                     timelines_map = {}
#                     for timeline_name, timeline in result.get("timelines", {}).items():
#                         timeline_db = Timeline.objects.get(id=timeline)
#                         old_timeline_id = timeline_db.id.hex
#                         # timeline_db.parent = None
#                         if timeline_db.plugin_run_result:
#                             plugin_run_result_db = timeline_db.plugin_run_result
#                             plugin_run_result_db.pk = None
#                             plugin_run_result_db.plugin_run = plugin_run_db
#                             plugin_run_result_db.save()
#                             timeline_db.plugin_run_result = plugin_run_result_db

#                         timeline_db.pk = None
#                         timeline_db.video = video_tgt_db
#                         timeline_db.save()

#                         for segment_db in TimelineSegment.objects.filter(
#                             timeline__id=old_timeline_id
#                         ):
#                             old_segment_id = segment_db.id.hex
#                             segment_db.pk = None
#                             segment_db.timeline = timeline_db
#                             segment_db.save()

#                             for (
#                                 segment_annotation_db
#                             ) in TimelineSegmentAnnotation.objects.filter(
#                                 timeline_segment__id=old_segment_id
#                             ):
#                                 old_segment_annotation_id = segment_annotation_db.id.hex

#                                 annotation_db = segment_annotation_db.annotation
#                                 category_db = None
#                                 if annotation_db.category:
#                                     category_db = annotation_db.category
#                                     category_db.pk = None
#                                     category_db.owner = new_owner
#                                     category_db.video = video_tgt_db
#                                     category_db.save()

#                                 annotation_db.pk = None
#                                 annotation_db.category = category_db
#                                 annotation_db.owner = new_owner
#                                 annotation_db.video = video_tgt_db
#                                 annotation_db.save()
#                                 segment_annotation_db.pk = None
#                                 segment_annotation_db.timeline_segment = segment_db
#                                 segment_annotation_db.annotation = annotation_db
#                                 segment_annotation_db.save()

#                         timelines_dict[timeline_name] = timeline_db.id.hex
#                         timelines_list.append(timeline_db)
#                         timelines_map[old_timeline_id] = timeline_db

#                     for timeline_db in timelines_list:
#                         if timeline_db.parent is None:
#                             continue

#                         timeline_db.parent = timelines_map[timeline_db.parent.id.hex]
#                         timeline_db.save()

#                     f.write(
#                         json.dumps(
#                             {
#                                 "video_id": video_tgt_db.id.hex,
#                                 "plugin": plugin_run["plugin"],
#                                 "status": plugin_run["status"],
#                                 "result": {
#                                     "plugin_run": plugin_run_db.id.hex,
#                                     "plugin_run_results": plugin_run_result_lists,
#                                     "timelines": timelines_dict,
#                                     "data": result["data"],
#                                 },
#                             }
#                         )
#                         + "\n"
#                     )

#                     print(plugin_run_db)

#         self.stdout.write(self.style.SUCCESS(f"User added"))
#         # else:
#         #     options["video"]
