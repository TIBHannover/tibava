from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import AudioData, ScalarData
from data import DataManager, Data

from typing import Callable, Optional, Dict
import numpy as np
import logging

default_config = {"data_dir": "/data/"}


default_parameters = {
    "sr": 8000,
    "max_samples": None,
    "hop_length": 512,
    "normalize": True,
}

requires = {
    "audio": AudioData,
}

provides = {
    "rms": ScalarData,
}


@AnalyserPluginManager.export("audio_rms_analysis")
class AudioRMSAnalysis(
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
        import librosa

        with (
            inputs["audio"] as input_data,
            data_manager.create_data("ScalarData") as output_data,
        ):
            with input_data.open_audio("r") as f_audio:
                y, sr = librosa.load(f_audio, sr=parameters.get("sr"))

                if parameters.get("max_samples"):
                    target_sr = sr / (len(y) / int(parameters.get("max_samples")))
                    try:
                        y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
                        sr = target_sr
                    except Exception as e:
                        logging.warning(
                            "[AudioRMSAnalysis] Resampling failed. Try numpy."
                        )
                        t = np.arange(y.shape[0]) / sr
                        t_target = (
                            np.arange(int(y.shape[0] / sr * target_sr)) / target_sr
                        )

                        y = np.interp(t_target, t, y)
                        sr = target_sr

                y = librosa.feature.rms(
                    y=y, hop_length=parameters.get("hop_length")
                ).squeeze()
                if parameters.get("normalize"):
                    y = (y - np.min(y)) / (np.max(y) - np.min(y))

                output_data.y = y
                output_data.time = np.arange(len(y)) * parameters.get("hop_length") / sr
                output_data.delta_time = parameters.get("hop_length") / sr
            return {"rms": output_data}
