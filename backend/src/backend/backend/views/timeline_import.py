import logging
import os
import traceback
import uuid
import xml.etree.ElementTree as ET


from django.views import View
from django.http import JsonResponse
from django.conf import settings

# from django.core.exceptions import BadRequest
from backend.utils import download_file
from backend.models import Timeline, TimelineSegment, TimelineSegmentAnnotation, Video, Annotation


logger = logging.getLogger(__name__)


def time_to_string(sec, loc="en"):
    sec, sec_frac = divmod(sec, 1)
    min, sec = divmod(sec, 60)
    hours, min = divmod(min, 60)

    sec_frac = round(1000 * sec_frac)
    hours = int(hours)
    min = int(min)
    sec = int(sec)

    if loc == "de":
        return f"{hours}:{min}:{sec},{sec_frac}"
    return f"{hours}:{min}:{sec}.{sec_frac}"


class TimelineImportEAF(View):
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                logger.error("TimelineImportEAF::not_authenticated")
                return JsonResponse({"status": "error"})

            if request.method != "POST":
                logger.error("TimelineImportEAF::wrong_method")
                return JsonResponse({"status": "error"})

            upload_id = uuid.uuid4().hex
            video_id = request.POST.get("video_id")
            print(video_id)
            try:
                video_db = Video.objects.get(id=video_id)
            except Video.DoesNotExist:
                return JsonResponse({"status": "error"})

            if "file" in request.FILES:
                output_dir = os.path.join(settings.MEDIA_ROOT)
                download_result = download_file(
                    output_dir=output_dir,
                    output_name=upload_id,
                    file=request.FILES["file"],
                    max_size=1024 * 1024 * 1024,  # 1GB
                    extensions=(".eaf"),
                )

                if download_result["status"] != "ok":
                    logger.error("TimelineImportEAF::download_failed")
                    return JsonResponse(download_result)

                print(download_result, flush=True)
                timelines = self.import_timelines_from_eaf(download_result["path"])
                for timeline in timelines:
                    timeline_db = Timeline.objects.create(
                        video=video_db, name=timeline["name"], order=Timeline.objects.filter(video=video_db).count()
                    )

                    for segment in timeline["segments"]:
                        segment_db = TimelineSegment.objects.create(
                            timeline=timeline_db, start=segment["start"], end=segment["end"]
                        )

                        if segment["label"] is None:
                            continue

                        annotation_db, created = Annotation.objects.get_or_create(
                            name=segment["label"], video=video_db, owner=request.user
                        )

                        tsa_db = TimelineSegmentAnnotation.objects.create(
                            timeline_segment=segment_db, annotation=annotation_db
                        )

                return JsonResponse(
                    {
                        "status": "ok",
                    }
                )

            return JsonResponse({"status": "error"})

        except Exception:
            logger.exception("Failed to import EAF timeline")
            return JsonResponse({"status": "error"})

    def import_timelines_from_eaf(self, xmlfile):
        # create element tree object
        tree = ET.parse(xmlfile)

        # get root element
        root = tree.getroot()

        # get time spans
        timeslots = {}
        for timeslot in root.findall("TIME_ORDER/TIME_SLOT"):
            timeslots[timeslot.attrib["TIME_SLOT_ID"]] = timeslot.attrib

        logger.debug(timeslots)

        # findall timelines
        timelines = []
        annotations = 0
        for timeline in root.findall("TIER"):
            timeline_segments = []

            for annotation in timeline.findall("ANNOTATION/ALIGNABLE_ANNOTATION"):
                start_time = timeslots[annotation.attrib["TIME_SLOT_REF1"]]["TIME_VALUE"]
                end_time = timeslots[annotation.attrib["TIME_SLOT_REF2"]]["TIME_VALUE"]

                for annotations_label in annotation:
                    timeline_segments.append(
                        {"start": int(start_time) / 1000, "end": int(end_time) / 1000, "label": annotations_label.text}
                    )
                    annotations += 1
            timelines.append({"name": timeline.attrib["TIER_ID"], "segments": timeline_segments})

        logger.debug(timelines)
        logger.info(f"{len(timelines)} timelines with {annotations} annotations found!")
        return timelines
