import base64
import io
import json
import pathlib
import uuid
import zipfile
from typing import Dict

import numpy as np
from django.conf import settings
from tibava_data import DataManager

from backend.exporter_manager import Exporter, ExporterManager
from backend.models import (
    ExporterRun,
    PluginRunResult,
    Timeline,
    TimelineSegment,
    Video,
)
from backend.utils.export import json_to_csv, time_to_string
from backend.utils.parser import Parser


@ExporterManager.export_parser("csv")
class CSVExporterParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "include_category": {"parser": bool, "default": True},
            "use_timestamps": {"parser": bool, "default": True},
            "use_seconds": {"parser": bool, "default": True},
        }
        super().__init__()


@ExporterManager.export_plugin("csv")
class CSVExporter(Exporter):
    def __init__(self):
        super().__init__()

        self.config = {
            "output_path": pathlib.Path("/tmp/"),
            "analyser_host": settings.GRPC_HOST,
            "analyser_port": settings.GRPC_PORT,
        }

    def __call__(
        self,
        parameters: Dict,
        video: Video = None,
        exporter_run: ExporterRun = None,
        **kwargs,
    ):
        print("CSV", flush=True)
        include_category = parameters.get("include_category", True)
        use_timestamps = parameters.get("use_timestamps", True)
        use_seconds = parameters.get("use_seconds", True)

        timeline_annotations = []
        timeline_names = []

        data_manager = DataManager("/predictions/")

        for timeline_db in Timeline.objects.filter(video=video):
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
                        annotations["annotations"].append(json.dumps(all_annotations))
                    else:
                        annotations["annotations"].append("")

            timeline_annotations.append(annotations)
            timeline_names.append(timeline_db.name)

        # print(len(timeline_annotations))

        # Create a temporary in-memory file to store the zip
        # buffer = io.BytesIO()
        output_path = (
            self.config.get("output_path")
            / f"{video.id.hex[:6]}_{uuid.uuid4().hex[:6]}.zip"
        )
        with open(
            output_path,
            "wb",
        ) as f:
            with zipfile.ZipFile(f, "w") as zip_file:
                # print(timeline_annotations)

                for index, json_obj in enumerate(timeline_annotations):
                    csv_data = json_to_csv(json_obj)
                    filename = f"{timeline_names[index]}.tsv"

                    # Write the CSV data to the individual file
                    zip_file.writestr(filename, csv_data)

                # # Close the zip file
                # zip_file.close()
