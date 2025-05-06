from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import ScalarData, ImageEmbeddings

import logging
import numpy as np
from data import DataManager, Data

from typing import Callable, Optional, Dict


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {"min_threshold": None, "max_threshold": None}

requires = {
    "scalar": ScalarData,
}

provides = {
    "scalar": ScalarData,
}


@AnalyserPluginManager.export("scalar_threshold")
class ScalarThreshold(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
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
        with (
            inputs["scalar"] as scalar_data,
            data_manager.create_data("ScalarData") as output_data,
        ):
            y = scalar_data.y

            if parameters["min_threshold"]:
                y[y < parameters["min_threshold"]] = parameters["min_threshold"]

            if parameters["max_threshold"]:
                y[y >= parameters["max_threshold"]] = parameters["max_threshold"]

            output_data.y = y
            output_data.time = scalar_data.time
            output_data.delta_time = scalar_data.delta_time
            return {"scalar": output_data}
