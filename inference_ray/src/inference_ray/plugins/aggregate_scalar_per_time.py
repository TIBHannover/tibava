from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import DataManager, Data
from data import ScalarData, ListData

from typing import Callable, Optional, Dict

import logging
import numpy as np


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {"aggregation": "or"}

requires = {
    "scalars": ListData,
}

provides = {
    "aggregated_scalars": ListData,
}


@AnalyserPluginManager.export("aggregate_list_scalar_per_time")
class AggregateListScalarPerTime(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config: dict = None, **kwargs):
        super().__init__(config, **kwargs)

    def aggregate_probs(self, y_per_t: dict, aggregation: str = "or") -> list:
        def aggregate_mean(y: list) -> np.array:
            return np.mean(y, axis=0)

        def aggregate_prod(y: list) -> np.array:
            return np.prod(y, axis=0)

        def aggregate_or(y: list) -> np.array:
            return 1 - np.prod(1 - y, axis=0)

        def aggregate_and(y: list) -> np.array:
            return np.prod(y, axis=0)

        aggregation_f = {
            "mean": aggregate_mean,
            "prod": aggregate_prod,
            "or": aggregate_or,
            "and": aggregate_and,
        }

        if aggregation not in aggregation_f:
            logging.error(
                "[AggregateScalarPerTime] Unknown aggregation method. Using <mean> instead."
            )
            aggregation = "mean"

        return [
            aggregation_f[aggregation](np.stack(y, axis=0)) for y in y_per_t.values()
        ]

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        with (
            inputs["scalars"] as input_data,
            data_manager.create_data("ListData") as output_data,
        ):
            aggregated_y = []

            for i, (index, data) in enumerate(input_data):
                with data:
                    y_per_t = {}
                    for n in range(len(data.time)):
                        if data.time[n] not in y_per_t:
                            y_per_t[data.time[n]] = []

                        y_per_t[data.time[n]].append(data.y[n])

                    aggregated_y.append(
                        self.aggregate_probs(
                            y_per_t, aggregation=parameters.get("aggregation")
                        )
                    )
                    self.update_callbacks(callbacks, progress=i / len(input_data))

            self.update_callbacks(callbacks, progress=1.0)

            for index, y in zip(input_data.index, aggregated_y):
                with output_data.create_data("ScalarData", index=index) as scalar_data:
                    scalar_data.y = np.asarray(y)
                    scalar_data.time = np.asarray(list(y_per_t.keys()))
                    scalar_data.delta_time = data.delta_time
            return {"aggregated_scalars": output_data}


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {"aggregation": "or"}

requires = {
    "scalar": ScalarData,
}

provides = {
    "aggregated_scalar": ScalarData,
}


@AnalyserPluginManager.export("aggregate_scalar_per_time")
class AggregateScalarPerTime(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config: dict = None, **kwargs):
        super().__init__(config, **kwargs)

    def aggregate_probs(self, y_per_t: dict, aggregation: str = "or") -> list:
        def aggregate_mean(y: list) -> np.array:
            return np.mean(y, axis=0)

        def aggregate_prod(y: list) -> np.array:
            return np.prod(y, axis=0)

        def aggregate_or(y: list) -> np.array:
            return 1 - np.prod(1 - y, axis=0)

        def aggregate_and(y: list) -> np.array:
            return np.prod(y, axis=0)

        aggregation_f = {
            "mean": aggregate_mean,
            "prod": aggregate_prod,
            "or": aggregate_or,
            "and": aggregate_and,
        }

        if aggregation not in aggregation_f:
            logging.error(
                "[AggregateScalarPerTime] Unknown aggregation method. Using <mean> instead."
            )
            aggregation = "mean"

        return [
            aggregation_f[aggregation](np.stack(y, axis=0)) for y in y_per_t.values()
        ]

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        with (
            inputs["scalar"] as input_data,
            data_manager.create_data("ScalarData") as scalar_data,
        ):
            with input_data as data:
                y_per_t = {}
                for n in range(len(data.time)):
                    if data.time[n] not in y_per_t:
                        y_per_t[data.time[n]] = []

                    y_per_t[data.time[n]].append(data.y[n])

                y = self.aggregate_probs(
                    y_per_t, aggregation=parameters.get("aggregation")
                )

            self.update_callbacks(callbacks, progress=1.0)

            scalar_data.y = np.asarray(y)
            scalar_data.time = np.asarray(list(y_per_t.keys()))
            scalar_data.delta_time = data.delta_time
            return {"aggregated_scalar": scalar_data}
