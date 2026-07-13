from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from tibava_data import AnnotationData, Annotation, AudioData, FacesData, VideoData

from tibava_data import DataManager, Data

from tibava_utils import VideoDecoder

import logging
from typing import Callable, Dict, List, Any
from pathlib import Path
import math
import sys
import numpy as np


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {
    "min_length": 3,
}

requires = {
    "shot_sizes": AnnotationData,
}

provides = {
    "intensify": AnnotationData,
}

SHOT_SIZE_LABELS = {
    "Extreme Close-Up": 0,
    "Close-Up": 1,
    "Medium Shot": 2,
    "Full Shot": 3,
    "Long Shot": 4,
    "p_ECU": 0,
    "p_CU": 1,
    "p_MS": 2,
    "p_FS": 3,
    "p_LS": 4,
}

# def detect_shot_intensification(shots, min_length=3):
#     results = []
#     n = len(shots)
#     i = 0

#     while i < n - 2:
#         sequence = []
#         A = SHOT_SIZE_LABELS[shots[i]]
#         B = SHOT_SIZE_LABELS[shots[i+1]]
#         # Check first two shots

#         if A > B:
#             print("##", shots[i], shots[i+1])
#             start = i
#             expected = SHOT_SIZE_LABELS[shots[i+1]]
#             j = i+2

#             # Follow pattern
#             while j < n:
#                 current = SHOT_SIZE_LABELS[shots[j]]
#                 print("####", shots[j-1], shots[j], current > expected)

#                 sequence.append(current)

#                 if current > expected:
#                     break

#                 expected =  SHOT_SIZE_LABELS[shots[j]]
#                 j += 1

#             length = j - start

#             if length >= min_length:
#                 results.append((start, j-1, sequence))
#                 i = j  # skip past this block
#                 continue

#         i += 1

#     return results

# # get all shot_reverse_shot results
# intensification_list = detect_shot_intensification(shot_annotations)


@AnalyserPluginManager.export("movie_pattern_intensify")
class MoviePatternIntensify(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.3",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        min_length = parameters.get("min_length")
        shot_annotations = []
        shot_start_end = []

        with (
            inputs["shot_sizes"] as shot_sizes,
            data_manager.create_data("AnnotationData") as intensify,
        ):
            for x in shot_sizes.annotations:
                for label in x.labels:
                    logging.error(label)
                    if label in SHOT_SIZE_LABELS:
                        shot_annotations.append(label)
                        shot_start_end.append([x.start, x.end])
            logging.error(shot_annotations)
            logging.error(shot_start_end)

            intensification_list = self.detect_shot_intensification(
                shot_annotations, min_length
            )

            logging.error(intensification_list)
            for shot in intensification_list:
                logging.error(shot)

                start = shot_start_end[shot[0]][0]
                end = shot_start_end[shot[1]][1]
                intensify.annotations.append(
                    Annotation(start=start, end=end, labels=["Intensification"])
                )
        return {
            "intensify": intensify,
        }

    def detect_shot_intensification(self, shots, min_length=3):
        results = []
        n = len(shots)
        i = 0

        while i < n - 2:
            sequence = []
            shot_size_shot_1 = SHOT_SIZE_LABELS[shots[i]]
            shot_size_shot_2 = SHOT_SIZE_LABELS[shots[i + 1]]
            # Check first two shots

            if shot_size_shot_1 > shot_size_shot_2:
                print("##", shots[i], shots[i + 1])
                start = i
                expected = SHOT_SIZE_LABELS[shots[i + 1]]
                j = i + 2

                # Follow pattern
                while j < n:
                    current = SHOT_SIZE_LABELS[shots[j]]
                    print("####", shots[j - 1], shots[j], current > expected)

                    sequence.append(current)

                    if current > expected:
                        break

                    expected = SHOT_SIZE_LABELS[shots[j]]
                    j += 1

                length = j - start

                if length >= min_length:
                    results.append((start, j - 1, sequence))
                    i = j  # skip past this block
                    continue

            i += 1

        return results
