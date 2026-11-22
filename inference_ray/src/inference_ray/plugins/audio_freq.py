import logging
from typing import Callable, Dict, Optional

import numpy as np
from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from tibava_data import AudioData, Data, DataManager, HistData, ScalarData

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

default_parameters = {
    "sr": 8000,
    "n_fft": 256,
    "normalize": True,
    "max_columns": 2000,
}


@AnalyserPluginManager.export("audio_freq_analysis")
class AudioFreqAnalysis(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.2",
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
        import math

        import librosa

        with (
            inputs["audio"] as input_data,
            data_manager.create_data("HistData") as output_data,
        ):
            with input_data.open_audio("r") as f_audio:
                y, sr = librosa.load(f_audio, sr=parameters.get("sr"))

            n_fft = parameters.get("n_fft")
            hop = n_fft // 4
            if len(y) < n_fft:
                y = np.pad(y, (0, n_fft - len(y)))
            n_frames = 1 + (len(y) - n_fft) // hop
            # number of STFT columns averaged into one heatmap column
            block = max(1, math.ceil(n_frames / parameters.get("max_columns")))

            columns = []
            frames_per_chunk = block * 32  # keeps memory low for long videos
            for f0 in range(0, n_frames, frames_per_chunk):
                f1 = min(f0 + frames_per_chunk, n_frames)
                segment = y[f0 * hop : (f1 - 1) * hop + n_fft]
                power = (
                    np.abs(
                        librosa.stft(segment, n_fft=n_fft, hop_length=hop, center=False)
                    )
                    ** 2
                )
                starts = np.arange(0, power.shape[1], block)
                sums = np.add.reduceat(power, starts, axis=1)
                counts = np.diff(np.append(starts, power.shape[1]))
                columns.append(sums / counts)  # mean power per heatmap column
                self.update_callbacks(callbacks, progress=f1 / n_frames)

            S_db = librosa.power_to_db(np.concatenate(columns, axis=1), ref=np.max)
            if parameters.get("normalize"):
                S_db = (S_db - np.min(S_db)) / (np.max(S_db) - np.min(S_db))

            delta_time = block * hop / sr
            output_data.hist = np.transpose(S_db)
            output_data.time = np.arange(S_db.shape[1]) * delta_time
            output_data.delta_time = delta_time
            return {"freq": output_data}
