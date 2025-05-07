from typing import Dict
import logging

from ..utils.analyser_client import TaskAnalyserClient

from backend.models import PluginRun, Video, Timeline
from backend.plugin_manager import PluginManager

from backend.utils.parser import Parser
from backend.utils.task import Task
from backend.utils import rgb_to_hex


from data import DataManager  # type: ignore
from backend.models import (
    Annotation,
    PluginRun,
    TimelineSegmentAnnotation,
    Video,
    TibavaUser,
    Timeline,
    TimelineSegment,
)
from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("text_pos")
class PoSTaggingParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "PoS Tagging"},
            "language_code": {"parser": str, "default": "de"},
        }


@PluginManager.export_plugin("text_pos")
class PoSTagging(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "analyser_host": settings.GRPC_HOST,
            "analyser_port": settings.GRPC_PORT,
        }

    def __call__(
        self,
        parameters: Dict,
        video: Video = None,
        user: TibavaUser = None,
        plugin_run: PluginRun = None,
        dry_run: bool = False,
        **kwargs,
    ):
        manager = DataManager(self.config["output_path"])
        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )

        video_id = self.upload_video(client, video)
        audio_result = self.run_analyser(
            client,
            "video_to_audio",
            inputs={"video": video_id},
            outputs=["audio"],
        )
        if audio_result is None:
            raise Exception

        if plugin_run is not None:
            plugin_run.progress = 0.3
            plugin_run.save()

        segmentation_result = self.run_analyser(
            client,
            "whisper_x",
            parameters={
                "language_code": None
            },  # TODO should whisper_x detect the language by itself (cached version can be used) or use explicitly set language for pos tags?
            inputs={**audio_result[0]},
            outputs=["annotations"],
        )
        if segmentation_result is None:
            raise Exception

        if plugin_run is not None:
            plugin_run.progress = 0.7
            plugin_run.save()

        result = self.run_analyser(
            client,
            "text_pos",
            parameters={"language_code": parameters.get("language_code")},
            inputs={
                "annotations": segmentation_result[0]["annotations"],
            },
            downloads=["annotations"],
        )

        if result is None:
            raise Exception

        def create_timelines(
            data,
            timelines_name: str,
            annotation_key: str,
            pos_tags: Dict[str, int],
        ):
            data.load()

            parent_timeline = Timeline.objects.create(
                video=video,
                name=timelines_name,
                type=Timeline.TYPE_ANNOTATION,
            )

            result_timelines = {}
            for tag, idx in pos_tags.items():
                timeline = Timeline.objects.create(
                    video=video,
                    name=tag,
                    type=Timeline.TYPE_ANNOTATION,
                    parent=parent_timeline,
                )
                result_timelines[f"{timelines_name}_{data.name}"] = timeline.id.hex
                for annotation in data.annotations:
                    timeline_segment_db = TimelineSegment.objects.create(
                        timeline=timeline,
                        start=annotation.start,
                        end=annotation.end,
                    )
                    for annotation_object in annotation.labels:
                        tag_count = annotation_object[annotation_key][idx]

                        max_tag_count = 100
                        color = max(0, (max_tag_count - tag_count) / max_tag_count)
                        hex_color = rgb_to_hex((color, color, color))

                        annotation_db, _ = Annotation.objects.get_or_create(
                            name=str(tag_count),
                            video=video,
                            owner=user,
                            color=hex_color,
                        )

                        TimelineSegmentAnnotation.objects.create(
                            annotation=annotation_db,
                            timeline_segment=timeline_segment_db,
                        )
            return result_timelines

        with transaction.atomic():
            result_timelines = {}
            with result[1]["annotations"] as data:
                # from plugin upos
                pos_abbreviations = {
                    "ADJ": 0,
                    "ADP": 1,
                    "ADV": 2,
                    "AUX": 3,
                    "CONJ": 4,
                    "CCONJ": 4,
                    "SCONJ": 4,
                    "DET": 5,
                    "INTJ": 6,
                    "NOUN": 7,
                    "NUM": 8,
                    "PART": 9,
                    "PRON": 10,
                    "PROPN": 11,
                    "VERB": 12,
                    "X": 13,
                    "PUNCT": 13,
                    "SYM": 13,
                }
                # from https://universaldependencies.org/u/pos/
                pos_names = {
                    "ADJ": "adjective",
                    "ADP": "adposition",
                    "ADV": "adverb",
                    "AUX": "auxiliary",
                    # "CCONJ": "coordinating conjunction",
                    # "SCONJ": "subordinating conjunction",
                    "CONJ": "conjunction",
                    "DET": "determiner",
                    "INTJ": "interjection",
                    "NOUN": "noun",
                    "NUM": "numeral",
                    "PART": "particle",
                    "PRON": "pronoun",
                    "PROPN": "proper noun",
                    "VERB": "verb",
                    # "SYM": "symbol",
                    # "PUNCT": "punctuation",
                    "X": "symbol, punctuation, other",
                }
                pos_dict = {}
                for abbreviation, idx in pos_abbreviations.items():
                    if abbreviation in pos_names.keys():
                        pos_dict[pos_names[abbreviation].title()] = idx

                result_timelines.update(
                    create_timelines(data, parameters["timeline"], "vector", pos_dict)
                )

            return {
                "plugin_run": plugin_run.id.hex,
                "plugin_run_results": [],
                "timelines": result_timelines,
                "data": {
                    "annotations": result[1]["annotations"].id,
                },
            }
