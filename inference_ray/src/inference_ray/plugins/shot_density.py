from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import ShotsData, ScalarData

import math
import numpy as np
from data import DataManager, Data

from typing import Callable, Optional, Dict

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {"kernel": "gaussian", "bandwidth": 30.0, "fps": 10}

requires = {
    "shots": ShotsData,
}

provides = {
    "shot_density": ScalarData,
}


@AnalyserPluginManager.export("shot_density")
class ShotDensity(
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
        from sklearn.neighbors import KernelDensity

        with (
            inputs["shots"] as shots_data,
            data_manager.create_data("ScalarData") as output_data,
        ):
            last_shot_end = 0
            shots = []
            for i, shot in enumerate(shots_data.shots):
                shots.append(shot.start)

                if shot.end > last_shot_end:
                    last_shot_end = shot.end

                self.update_callbacks(callbacks, progress=i / len(shots_data.shots))

            time = np.linspace(
                0, last_shot_end, math.ceil(last_shot_end * parameters.get("fps")) + 1
            )[:, np.newaxis]
            shots = np.asarray(shots).reshape(-1, 1)
            kde = KernelDensity(
                kernel=parameters.get("kernel"), bandwidth=parameters.get("bandwidth")
            ).fit(shots)
            log_dens = kde.score_samples(time)
            shot_density = np.exp(log_dens)
            shot_density = (shot_density - shot_density.min()) / (
                shot_density.max() - shot_density.min()
            )

            self.update_callbacks(callbacks, progress=1.0)
            output_data.y = shot_density.squeeze()
            output_data.time = time.squeeze()
            output_data.delta_time = 1 / parameters.get("fps")
            return {"shot_density": output_data}
