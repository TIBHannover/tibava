from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import AudioData, AnnotationData, Annotation

from data import DataManager, Data

from typing import Callable, Optional, Dict
import logging

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {"sr": 16000, "chunk_length": 30}

requires = {
    "audio": AudioData,
}

provides = {
    "annotations": AnnotationData,
}


@AnalyserPluginManager.export("whisper")
class Whisper(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        # inference_config = self.config.get("inference", None)
        # self.server = InferenceServer.build(inference_config.get("type"), inference_config.get("params", {}))

        self.model = None
        self.model_name = self.config.get("model", "openai/whisper-base")

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import librosa
        import torch
        from transformers import pipeline

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        if self.model is None:
            self.model = pipeline(
                "automatic-speech-recognition",
                model=self.model_name,
                chunk_length_s=30,
                device=device,
            )
            self.device = device

        with (
            inputs["audio"] as input_data,
            data_manager.create_data("AnnotationData") as output_data,
        ):
            with input_data.open_audio("r") as f_audio:
                y, sr = librosa.load(f_audio, sr=parameters.get("sr"))

                prediction = self.model(
                    y,
                    batch_size=8,
                    return_timestamps=True,
                    generate_kwargs={"task": "transcribe"},
                )["chunks"]

                for chunk in prediction:
                    start = chunk["timestamp"][0]
                    end = chunk["timestamp"][1]
                    if start is None:
                        start = 0.0
                    if end is None:
                        end = len(y) / sr
                    output_data.annotations.append(
                        Annotation(start=start, end=end, labels=[str(chunk["text"])])
                    )

                self.update_callbacks(callbacks, progress=1.0)
                return {"annotations": output_data}
