from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager

from data import Annotation, AnnotationData, ShotsData, ScalarData

import numpy as np
from data import DataManager, Data

from typing import Callable, Optional, Dict


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "shot_type_classifier",
}

default_parameters = {}

requires = {
    "shots": ShotsData,
    "scalar": ScalarData,
}

provides = {
    "annotations": AnnotationData,
}


@AnalyserPluginManager.export("shot_scalar_annotator")
class ShotScalarAnnotator(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        self.host = self.config["host"]
        self.port = self.config["port"]

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        with (
            inputs["shots"] as shots_data,
            inputs["scalar"] as scalar_data,
            data_manager.create_data("AnnotationData") as output_data,
        ):
            y = np.asarray(scalar_data.y)
            time = np.asarray(scalar_data.time)
            for i, shot in enumerate(shots_data.shots):
                shot_y_data = y[np.logical_and(time >= shot.start, time <= shot.end)]

                if len(shot_y_data) <= 0:
                    continue

                y_mean = np.mean(shot_y_data)
                output_data.annotations.append(
                    Annotation(start=shot.start, end=shot.end, labels=[str(y_mean)])
                )  # Maybe store max_mean_class_prob as well?
                self.update_callbacks(callbacks, progress=i / len(shots_data.shots))

            self.update_callbacks(callbacks, progress=1.0)
            return {"annotations": output_data}
