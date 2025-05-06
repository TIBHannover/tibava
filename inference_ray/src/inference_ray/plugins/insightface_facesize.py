from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import (
    BboxesData,
    ListData,
    ScalarData,
    AnnotationData,
    Annotation,
    ShotsData,
)

import numpy as np
from data import DataManager, Data

from typing import Callable, Optional, Dict

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {"reduction": "max"}

requires = {
    "bboxes": BboxesData,
    "shot_annotation": AnnotationData,
    "shots": ShotsData,
}

provides = {
    "probs": ListData,
    "facesizes": ScalarData,
}


@AnalyserPluginManager.export("insightface_facesize")
class InsightfaceFacesize(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        # self.host = self.config["host"]
        # self.port = self.config["port"]

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        with (
            inputs["bboxes"] as bbox_data,
            inputs["shot_annotation"] as shot_annotation,
            inputs["shots"] as shots,
            data_manager.create_data("AnnotationData") as facesizes_data,
        ):
            facesizes_dict = {}
            delta_time = None

            for i, bbox in enumerate(bbox_data.bboxes):
                if bbox.time not in facesizes_dict:
                    facesizes_dict[bbox.time] = []
                facesizes_dict[bbox.time].append(bbox.w * bbox.h)
                delta_time = bbox.delta_time

            if parameters.get("reduction") == "max":
                facesizes = [np.max(x).tolist() for x in facesizes_dict.values()]
            else:  # parameters.get("reduction") == "mean":
                facesizes = [np.mean(x).tolist() for x in facesizes_dict.values()]

            for shot_index, shot in enumerate(shots.shots):
                faces_in_annotation = [
                    t for t in facesizes_dict.keys() if t >= shot.start and t < shot.end
                ]
                if len(faces_in_annotation) > 0:
                    face_label = shot_annotation.annotations[shot_index].labels[0]
                else:
                    face_label = "None"

                facesizes_data.annotations.append(
                    Annotation(start=shot.start, end=shot.end, labels=[face_label])
                )

                self.update_callbacks(callbacks, progress=1.0 / len(shots.shots))

            facesizes_data.y = facesizes
            facesizes_data.time = list(facesizes_dict.keys())

            return {
                "annotations": facesizes_data,
            }
