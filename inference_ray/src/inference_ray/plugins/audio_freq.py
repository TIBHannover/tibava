from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import AudioData, ScalarData, HistData
from data import DataManager, Data

from typing import Callable, Optional, Dict
import numpy as np
import logging

default_config = {"data_dir": "/data/"}


default_parameters = {
    "sr": 8000,
    "max_samples": 100000,
    "normalize": True,
    "n_fft": 256,
}

requires = {
    "audio": AudioData,
}

provides = {
    "freq": HistData,
}


@AnalyserPluginManager.export("audio_freq_analysis")
class AudioFreqAnalysis(
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
            data_manager.create_data("HistData") as output_data,
        ):
            with input_data.open_audio("r") as f_audio:
                y, sr = librosa.load(f_audio, sr=parameters.get("sr"))

            if parameters.get("max_samples"):
                target_sr = sr / (len(y) / int(parameters.get("max_samples")))

                y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
                sr = target_sr

            S = np.abs(librosa.stft(y, n_fft=parameters.get("n_fft")))
            S_db = librosa.amplitude_to_db(S, ref=np.max)

            time = y.shape[0] / sr
            t_delta = time / S_db.shape[1]

            if parameters.get("normalize"):
                S_db = (S_db - np.min(S_db)) / (np.max(S_db) - np.min(S_db))

            S_db = np.transpose(S_db)

            output_data.hist = S_db
            output_data.time = np.arange(S_db.shape[0]) * t_delta
            output_data.delta_time = 1 / sr

            return {"freq": output_data}
