import json
import logging
import traceback
import logging
import sys
import io
import csv
import base64
from dataclasses import dataclass

from typing import List, Tuple

from django.views import View
from django.http import JsonResponse
from django.conf import settings

from pympi.Elan import Eaf, to_eaf
from io import StringIO
import pandas as pd

import zipfile

from backend.utils.color import get_closest_color
from backend.models import (
    Video,
    Annotation,
    Timeline,
    TimelineSegment,
    PluginRunResult,
    PluginRun,
)
from enum import Enum
from data import DataManager, Shot
import numpy as np


logger = logging.getLogger(__name__)


def json_to_csv(json_obj):
    df = pd.DataFrame(json_obj)
    return df.to_csv(index=False, sep="\t")


def time_to_string(sec, loc="en"):
    sec, sec_frac = divmod(sec, 1)
    min, sec = divmod(sec, 60)
    hours, min = divmod(min, 60)

    sec_frac = round(1000 * sec_frac)
    hours = (2 - len(str(int(hours)))) * "0" + str(int(hours))
    min = (2 - len(str(int(min)))) * "0" + str(int(min))
    sec = (2 - len(str(int(sec)))) * "0" + str(int(sec))

    if loc == "de":
        return f"{hours}:{min}:{sec},{sec_frac}"
    return f"{hours}:{min}:{sec}.{sec_frac}"


@dataclass
class TimeExport:
    start: int
    end: int


@dataclass
class TimelineExport:
    annotations: List[str]
    headlines: List[str]


class TimeFormatExport(Enum):
    SECOND = 1
    ISO = 2


class TimeTypeExport(Enum):
    START = 1
    END = 2
    DURATION = 3
    DURATION_NO_GAP = 4


class VideoExport(View):

    def get_segment_times_from_timeline(
        self, video: Video, timeline_id: str = None
    ) -> List[TimeExport]:
        times = []
        if timeline_id:
            timeline_db = Timeline.objects.get(id=timeline_id)
            timeline_segments = timeline_db.timelinesegment_set.all()
            for index, segment_db in enumerate(timeline_segments):
                times.append(TimeExport(start=segment_db.start, end=segment_db.end))
        else:
            plugin_run_result_db = PluginRunResult.objects.filter(
                type=PluginRunResult.TYPE_SHOTS, plugin_run__video=video
            ).first()
            if plugin_run_result_db is not None:

                data_manager = DataManager(settings.DATA_OUTPUT_PATH)

                with data_manager.load(plugin_run_result_db.data_id) as shot_data:

                    for shot in shot_data.shots:
                        times.append(TimeExport(start=shot.start, end=shot.end))
            else:
                # this is some old stuff

                timeline_db = Timeline.objects.filter(
                    type=Timeline.TYPE_ANNOTATION, video=video
                ).first()
                timeline_segments = timeline_db.timelinesegment_set.all()
                for index, segment_db in enumerate(timeline_segments):
                    times.append(TimeExport(start=segment_db.start, end=segment_db.end))

        return times

    def export_time_annotations(
        self,
        video: Video,
        segments: List[TimeExport] = None,
        type: TimeTypeExport = None,
        format: TimeFormatExport = None,
    ):
        times = [s.start for s in segments] + [video.duration]
        durations_no_gap = np.asarray(times[1:]) - np.asarray(times[:-1])
        durations = np.asarray([s.end for s in segments]) - np.asarray(
            [s.start for s in segments]
        )

        if type is None:
            type = TimeTypeExport.START
        if format is None:
            format = TimeFormatExport.SECOND

        if format == TimeFormatExport.ISO:
            if type == TimeTypeExport.START:
                return TimelineExport(
                    headlines=["start hh:mm:ss.ms"],
                    annotations=[time_to_string(t.start, loc="en") for t in segments],
                )
            elif type == TimeTypeExport.END:
                return TimelineExport(
                    headlines=["end hh:mm:ss.ms"],
                    annotations=[time_to_string(t.end, loc="en") for t in segments],
                )
            elif type == TimeTypeExport.DURATION:
                return TimelineExport(
                    headlines=["duration hh:mm:ss.ms"],
                    annotations=[time_to_string(t, loc="en") for t in durations],
                )
            elif type == TimeTypeExport.DURATION_NO_GAP:
                return TimelineExport(
                    headlines=["duration to next segment hh:mm:ss.ms"],
                    annotations=[time_to_string(t, loc="en") for t in durations_no_gap],
                )

        elif format == TimeFormatExport.SECOND:
            if type == TimeTypeExport.START:
                return TimelineExport(
                    headlines=["start in seconds"],
                    annotations=[t.start for t in segments],
                )
            elif type == TimeTypeExport.END:
                return TimelineExport(
                    headlines=["end in seconds"],
                    annotations=[t.end for t in segments],
                )
            elif type == TimeTypeExport.DURATION:
                return TimelineExport(
                    headlines=["duration in seconds"],
                    annotations=[t for t in durations],
                )
            elif type == TimeTypeExport.DURATION_NO_GAP:
                return TimelineExport(
                    headlines=["duration to next segment in seconds"],
                    annotations=[t for t in durations_no_gap],
                )

    def export_scalar_timeline(
        self,
        timeline: Timeline,
        plugin_run_reuslts: PluginRunResult,
        segments: List[TimeExport] = None,
        **kwargs,
    ):
        data_manager = DataManager(settings.DATA_OUTPUT_PATH)

        headlines = [timeline.name]

        annotations = []
        with data_manager.load(plugin_run_reuslts.data_id) as data:
            y = np.asarray(data.y)
            time = np.asarray(data.time)
            for segment in segments:
                shot_y_data = y[
                    np.logical_and(time >= segment.start, time <= segment.end)
                ]

                if len(shot_y_data) <= 0:
                    annotations.append(0.0)
                    continue

                y_agg = np.mean(shot_y_data)

                anno = y_agg.item()
                annotations.append(anno)

        return TimelineExport(headlines=headlines, annotations=annotations)

    def export_annotation_timeline(
        self,
        timeline: Timeline,
        segments: List[TimeExport] = None,
        include_category: bool = True,
        empty_annotation: str = None,
        **kwargs,
    ) -> TimelineExport:
        if empty_annotation is None:
            empty_annotation = "None"

        headlines = [timeline.name]

        annotations = []
        for segment_db in timeline.timelinesegment_set.all():
            annotation_labels = []
            for segment_annotation_db in segment_db.timelinesegmentannotation_set.all():

                if include_category and segment_annotation_db.annotation.category:
                    annotation_labels.append(
                        segment_annotation_db.annotation.category.name
                        + "::"
                        + segment_annotation_db.annotation.name
                    )
                else:
                    annotation_labels.append(segment_annotation_db.annotation.name)

            if len(annotation_labels) > 0:
                annotations.append(
                    {
                        "annotation": "+".join(annotation_labels),
                        "start": float(segment_db.start),
                        "end": float(segment_db.end),
                    }
                )
            else:
                annotations.append(
                    {
                        "annotation": empty_annotation,
                        "start": float(segment_db.start),
                        "end": float(segment_db.end),
                    }
                )

        # change segmentation if the user ask for another timeline segmentation
        if segments:
            new_annotations = []
            for segment in segments:
                new_annotation_labels = []

                for annotation in annotations:
                    if (
                        (
                            annotation["start"] >= segment.start
                            and annotation["start"] <= segment.end
                        )
                        or (
                            annotation["end"] >= segment.start
                            and annotation["end"] <= segment.end
                        )
                        or (
                            annotation["start"] <= segment.start
                            and annotation["end"] >= segment.end
                        )
                    ):
                        new_annotation_labels.append(annotation["annotation"])
                if len(new_annotation_labels) <= 0:
                    col_text = empty_annotation
                else:
                    col_text = "+".join(new_annotation_labels)
                # print(f'################ {col_text} {segment["end"]} {segment["annotation"]} {s} {d}')
                new_annotations.append(col_text)

            annotations = new_annotations

        return TimelineExport(headlines=headlines, annotations=annotations)

    def export_timeline(
        self,
        timeline: Timeline,
        segments: List[TimeExport] = None,
        **kwargs,
    ) -> TimelineExport:
        plugin_run_reuslts_db = timeline.plugin_run_result

        if plugin_run_reuslts_db:
            if plugin_run_reuslts_db.type == PluginRunResult.TYPE_SCALAR:
                return self.export_scalar_timeline(
                    timeline=timeline,
                    plugin_run_reuslts=plugin_run_reuslts_db,
                    segments=segments,
                    **kwargs,
                )
        else:
            return self.export_annotation_timeline(
                timeline=timeline, segments=segments, **kwargs
            )

    def export_merged_csv(self, parameters, video_db):
        include_category = parameters.get("include_category", True)
        use_timestamps = parameters.get("use_timestamps", True)
        use_seconds = parameters.get("use_seconds", True)
        merge_timeline = parameters.get("merge_timeline", True)
        split_places = parameters.get("split_places", False)
        import time

        t = time.time()
        start_time = time.time()
        # TODO timeline selection
        time_segments = self.get_segment_times_from_timeline(video=video_db)

        cols = []

        if True:
            cols.append(
                TimelineExport(
                    headlines=["#"],
                    annotations=[i for i, _ in enumerate(time_segments)],
                )
            )

        print(f"A {time.time()-t}")
        t = time.time()

        if use_seconds:
            cols.append(
                self.export_time_annotations(
                    video=video_db,
                    segments=time_segments,
                    type=TimeTypeExport.START,
                    format=TimeFormatExport.SECOND,
                )
            )
            cols.append(
                self.export_time_annotations(
                    video=video_db,
                    segments=time_segments,
                    type=TimeTypeExport.START,
                    format=TimeFormatExport.ISO,
                )
            )
            cols.append(
                self.export_time_annotations(
                    video=video_db,
                    segments=time_segments,
                    type=TimeTypeExport.END,
                    format=TimeFormatExport.SECOND,
                )
            )
            cols.append(
                self.export_time_annotations(
                    video=video_db,
                    segments=time_segments,
                    type=TimeTypeExport.END,
                    format=TimeFormatExport.ISO,
                )
            )
            cols.append(
                self.export_time_annotations(
                    video=video_db,
                    segments=time_segments,
                    type=TimeTypeExport.DURATION_NO_GAP,
                    format=TimeFormatExport.SECOND,
                )
            )
            cols.append(
                self.export_time_annotations(
                    video=video_db,
                    segments=time_segments,
                    type=TimeTypeExport.DURATION_NO_GAP,
                    format=TimeFormatExport.ISO,
                )
            )
            cols.append(
                self.export_time_annotations(
                    video=video_db,
                    segments=time_segments,
                    type=TimeTypeExport.DURATION,
                    format=TimeFormatExport.SECOND,
                )
            )
            cols.append(
                self.export_time_annotations(
                    video=video_db,
                    segments=time_segments,
                    type=TimeTypeExport.DURATION,
                    format=TimeFormatExport.ISO,
                )
            )

        print(f"B {time.time()-t}")
        t = time.time()
        for timeline_db in (
            video_db.timeline_set.all()
            .prefetch_related("timelinesegment_set")
            .prefetch_related("timelinesegment_set__timelinesegmentannotation_set")
            .prefetch_related(
                "timelinesegment_set__timelinesegmentannotation_set__annotation"
            )
            .prefetch_related(
                "timelinesegment_set__timelinesegmentannotation_set__annotation__category"
            )
        ):
            cols.append(
                self.export_timeline(timeline=timeline_db, segments=time_segments)
            )

            print(f"{timeline_db.name} {time.time()-t}")
            t = time.time()

        csv_cols = []
        for col in cols:
            if col is None:
                continue
            # print(f"{col.headlines} {len(col.headlines)} {len(col.annotations)}")
            csv_cols.append(col.headlines + col.annotations)

        rows = list(map(list, zip(*csv_cols)))

        buffer = io.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        for line in rows:
            writer.writerow(line)

        print(f"C {time.time()-t}")
        print(f"TOTAL {time.time()-start_time}")

        return buffer.getvalue()

    def export_individual_csv(self, parameters, video_db):
        include_category = parameters.get("include_category", True)
        use_timestamps = parameters.get("use_timestamps", True)
        use_seconds = parameters.get("use_seconds", True)

        timeline_annotations = []
        timeline_names = []

        data_manager = DataManager("/predictions/")

        for timeline_db in Timeline.objects.filter(video=video_db):
            annotations = {}
            tl_type = timeline_db.plugin_run_result
            # print(f"{timeline_db.name} --> {tl_type=}")

            # if the type of the timeline is scalar convert it to elan format
            if tl_type is not None:
                annotations["start in seconds"] = []
                if use_timestamps:
                    annotations["start hh:mm:ss.ms"] = []
                annotations["annotations"] = []

                data = data_manager.load(timeline_db.plugin_run_result.data_id)

                # if it is not of type SCALAR, skip it
                with data:
                    if tl_type.type == PluginRunResult.TYPE_SCALAR:
                        y = np.asarray(data.y)
                        # print(f"Data {len(y)}\n {y}")
                        time = np.asarray(data.time)
                        # print(f"Data {len(time)}\n {time}")
                        for i, time_stamp in enumerate(time):
                            annotations["start in seconds"].append(time_stamp)
                            annotations["annotations"].append(round(float(y[i]), 5))
                            if use_timestamps:
                                annotations["start hh:mm:ss.ms"].append(
                                    time_to_string(time_stamp, loc="en")
                                )
                    elif tl_type.type == PluginRunResult.TYPE_RGB_HIST:
                        colors = np.asarray(data.colors)
                        # print(f"Data {len(colors)}\n {colors}")
                        time = np.asarray(data.time)
                        # print(f"Data {len(time)}\n {time}")
                        for i, time_stamp in enumerate(time):
                            annotations["start in seconds"].append(time_stamp)
                            annotations["annotations"].append(colors[i])
                            if use_timestamps:
                                annotations["start hh:mm:ss.ms"].append(
                                    time_to_string(time_stamp, loc="en")
                                )
                    else:
                        continue

            else:
                times = []
                durations = []

                shot_timeline_segments = TimelineSegment.objects.filter(
                    timeline=timeline_db
                )

                for segment in shot_timeline_segments:
                    times.append(segment.start)
                    durations.append(segment.end - segment.start)

                time_duration = sorted(
                    list(set(zip(times, durations))), key=lambda x: x[0]
                )

                # start
                if use_timestamps:
                    annotations["start hh:mm:ss.ms"] = [
                        time_to_string(t[0], loc="en") for t in time_duration
                    ]

                if use_seconds:
                    annotations["start in seconds"] = [str(t[0]) for t in time_duration]

                # duration
                if use_timestamps:
                    annotations["duration hh:mm:ss.ms"] = [
                        time_to_string(t[1], loc="en") for t in time_duration
                    ]

                if use_seconds:
                    annotations["duration in seconds"] = [
                        str(t[1]) for t in time_duration
                    ]

                annotations["annotations"] = []

                for segment in shot_timeline_segments:
                    if len(segment.timelinesegmentannotation_set.all()) > 0:
                        all_annotations = []
                        for (
                            segment_annotation_db
                        ) in segment.timelinesegmentannotation_set.all():
                            if (
                                include_category
                                and segment_annotation_db.annotation.category
                            ):
                                all_annotations.append(
                                    segment_annotation_db.annotation.category.name
                                    + "::"
                                    + segment_annotation_db.annotation.name
                                )
                            else:
                                all_annotations.append(
                                    segment_annotation_db.annotation.name
                                )
                        annotations["annotations"].append(all_annotations)
                    else:
                        annotations["annotations"].append("")

            timeline_annotations.append(annotations)
            timeline_names.append(timeline_db.name)

        # print(len(timeline_annotations))

        # Create a temporary in-memory file to store the zip
        buffer = io.BytesIO()
        zip_file = zipfile.ZipFile(buffer, "w")

        # print(timeline_annotations)

        for index, json_obj in enumerate(timeline_annotations):
            csv_data = json_to_csv(json_obj)
            filename = f"{timeline_names[index]}.tsv"

            # Write the CSV data to the individual file
            zip_file.writestr(filename, csv_data)

        # Close the zip file
        zip_file.close()

        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def export_elan(self, parameters, video_db):
        eaf = Eaf(author="")
        eaf.remove_tier("default")
        eaf.add_linked_file(file_path=f"{video_db.id.hex}.mp4", mimetype="video/mp4")

        # get the boundary information from the timeline selected in parameters
        try:
            shot_timeline_db = Timeline.objects.get(
                id=parameters.get("shot_timeline_id")
            )
        except Timeline.DoesNotExist:
            raise Exception

        aggregation = ["max", "min", "mean"][parameters.get("aggregation")]

        # if the timeline is not of type annotation, raise an Exception
        if shot_timeline_db.type != Timeline.TYPE_ANNOTATION:
            raise Exception

        # get the shots from the boundary timeline
        shots = []
        shot_timeline_segments = TimelineSegment.objects.filter(
            timeline=shot_timeline_db
        )
        for x in shot_timeline_segments:
            shots.append(Shot(start=x.start, end=x.end))

        data_manager = DataManager("/predictions/")

        # for all timelines
        for timeline_db in Timeline.objects.filter(video=video_db):
            tier = timeline_db.name

            # ignore timelines with the same name TODO: check if there is a better way
            if tier in list(eaf.tiers.keys()):
                continue
            eaf.add_tier(tier_id=tier)
            # store all annotations

            tl_type = timeline_db.plugin_run_result

            # if the type of the timeline is scalar convert it to elan format
            if tl_type is not None:
                # if it is not of type SCALAR, skip it
                if tl_type.type != PluginRunResult.TYPE_SCALAR:
                    continue

                scalar_data = data_manager.load(timeline_db.plugin_run_result.data_id)
                with scalar_data:
                    y = np.asarray(scalar_data.y)
                    time = np.asarray(scalar_data.time)
                    for i, shot in enumerate(shots):
                        annotations = []
                        shot_y_data = y[
                            np.logical_and(time >= shot.start, time <= shot.end)
                        ]
                        # print(f"{shot.start} - {shot.end}")

                        if len(shot_y_data) <= 0:
                            continue

                        y_agg = 0

                        if aggregation == "mean":
                            y_agg = np.mean(shot_y_data)
                        if aggregation == "max":
                            y_agg = np.max(shot_y_data)
                        if aggregation == "min":
                            y_agg = np.min(shot_y_data)

                        start_time = int(shot.start * 1000)
                        end_time = int(shot.end * 1000)
                        anno = str(round(float(y_agg), 3))

                        annotations.append(f"value:{anno}")
                        if len(annotations) > 0:
                            eaf.add_annotation(
                                tier,
                                start=start_time,
                                end=end_time,
                                value=", ".join(annotations),
                            )
            # if it is an annotation timeline already, just export it
            else:
                for id, segment_db in enumerate(timeline_db.timelinesegment_set.all()):
                    start_time = int(segment_db.start * 1000)
                    end_time = int(segment_db.end * 1000)
                    # print(f"{start_time} - {end_time}")
                    # TODO: check why this occurs
                    if start_time == end_time:
                        continue
                    annotations = []
                    # if the timeline contains annotations, export them
                    if len(segment_db.timelinesegmentannotation_set.all()) > 0:
                        annotations = []
                        for (
                            segment_annotation_db
                        ) in segment_db.timelinesegmentannotation_set.all():
                            category = segment_annotation_db.annotation.category
                            name = segment_annotation_db.annotation.name
                            if category is not None:
                                anno = f"{category.name}:{name}"
                            else:
                                anno = f"{name}"
                            annotations.append(anno)
                        if len(annotations) > 0:
                            eaf.add_annotation(
                                tier,
                                start=start_time,
                                end=end_time,
                                value="; ".join(annotations),
                            )
                    else:
                        # if it does not contain annotations, export the boundaries with placeholder values (here: shot number)
                        eaf.add_annotation(
                            tier, start=start_time, end=end_time, value=f"value:{id}"
                        )

        stdout = sys.stdout
        sys.stdout = str_out = StringIO()
        to_eaf(file_path="-", eaf_obj=eaf)
        sys.stdout = stdout
        result = str_out.getvalue()

        return result

    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({"status": "error"})

            if "video_id" not in request.POST:
                return JsonResponse({"status": "error", "type": "missing_values"})

            try:
                video_db = Video.objects.get(id=request.POST.get("video_id"))
            except Video.DoesNotExist:
                return JsonResponse({"status": "error", "type": "not_exist"})

            if "format" not in request.POST:
                return JsonResponse({"status": "error", "type": "missing_values"})

            parameters = {}
            if "parameters" in request.POST:
                if isinstance(request.POST.get("parameters"), str):
                    try:
                        input_parameters = json.loads(request.POST.get("parameters"))
                    except:
                        return JsonResponse(
                            {"status": "error", "type": "wrong_request_body"}
                        )
                elif isinstance(request.POST.get("parameters"), (list, set)):
                    input_parameters = request.POST.get("parameters")
                else:
                    return JsonResponse(
                        {"status": "error", "type": "wrong_request_body"}
                    )

                for p in input_parameters:
                    if "name" not in p:
                        return JsonResponse(
                            {"status": "error", "type": "missing_values"}
                        )
                    if "value" not in p:
                        return JsonResponse(
                            {"status": "error", "type": "missing_values"}
                        )
                    parameters[p["name"]] = p["value"]

            if request.POST.get("format") == "merged_csv":
                result = self.export_merged_csv(parameters, video_db)
                return JsonResponse(
                    {"status": "ok", "file": result, "extension": "csv"}
                )

            elif request.POST.get("format") == "individual_csv":
                result = self.export_individual_csv(parameters, video_db)
                return JsonResponse(
                    {"status": "ok", "file": result, "extension": "zip"}
                )

            elif request.POST.get("format") == "elan":
                result = self.export_elan(parameters, video_db)
                return JsonResponse(
                    {"status": "ok", "file": result, "extension": "eaf"}
                )

            return JsonResponse({"status": "error", "type": "unknown_format"})
        except Exception:
            logger.exception("Failed to generate merged export")
            return JsonResponse({"status": "error"})
