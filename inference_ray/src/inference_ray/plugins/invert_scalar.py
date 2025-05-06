from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import ScalarData, ListData
from data import DataManager, Data

from typing import Callable, Optional, Dict

import logging
import numpy as np


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {"aggregation": "prod"}

requires = {
    "input": ScalarData,
}

provides = {
    "output": ScalarData,
}


@AnalyserPluginManager.export("invert_scalar")
class InvertScalar(
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
            inputs["input"] as input_data,
            data_manager.create_data("ScalarData") as output_data,
        ):
            y = input_data.y

            if np.max(y) > 1.0 or np.min(y) < 0.0:
                y = (y - np.min(y)) / (np.max(y) - np.min(y))

            output_data.y = 1 - y
            output_data.time = input_data.time
            output_data.delta_time = input_data.delta_time

            self.update_callbacks(callbacks, progress=1.0)
            return {"output": output_data}
