from typing import List, Any, Tuple, Callable, Dict
from pathlib import Path

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager  # type: ignore
from data import AudioData, ListData, AnnotationData, Annotation  # type: ignore

from data import DataManager, Data  # type: ignore

import logging

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "save_dir": Path("/models/audio_gender/"),
    "label_map": {0: "female", 1: "male"},
}

default_parameters = {}

requires = {
    "audio": AudioData,
    "annotations": ListData,
}

provides = {
    "annotations": AnnotationData,
}


@AnalyserPluginManager.export("audio_gender")
class AudioGender(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

        self.gender_model = None
        self.gender_processor = None

        self.model_name = self.config.get("model", "audio_gender_model")

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import librosa
        import torch
        import numpy as np
        from transformers import (
            Wav2Vec2FeatureExtractor,
            Wav2Vec2ForSequenceClassification,
        )

        device = "cuda:0" if torch.cuda.is_available() else "cpu"

        def get_models() -> Tuple[Any, Any]:
            gen_model = Wav2Vec2ForSequenceClassification.from_pretrained(
                "alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech",
                cache_dir=self.config.get("save_dir"),
            )
            gen_proc = Wav2Vec2FeatureExtractor.from_pretrained(
                "alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech",
                cache_dir=self.config.get("save_dir"),
            )
            # TODO wav2vec models are still saved in plugins/
            gen_model.to(device)
            gen_model.eval()
            return gen_model, gen_proc

        def classify_segments(
            audio_array: np.ndarray,
            speaker_turns: List[Annotation],
            sampling_rate: int,
        ) -> Tuple[List[Annotation], List[Annotation]]:
            """
            Takes Speaker Diarization segments and classifies them into speech male and female.

            Args:
                audio_array (np.ndarray): Loaded audio series
                speaker_turns (List[Annotation]): List of speaker segments from ASR
                sampling_rate (int): Sampling rate of audio_array

            Returns:
                List[Annotation]: List of gender predictions
            """
            gender_predictions = []

            for seg in speaker_turns:
                # slice audio of current segment
                segment_boundaries = librosa.time_to_samples(
                    np.array([seg.start, seg.end]), sr=sampling_rate
                )
                seg_audio_array = audio_array[
                    segment_boundaries[0] : segment_boundaries[1]
                ]
                seg_audio_tensor = (
                    torch.tensor(seg_audio_array).unsqueeze(0).to(torch.float32)
                )

                if seg_audio_tensor.shape[1] < sampling_rate:
                    seg_audio_tensor = torch.nn.functional.pad(
                        seg_audio_tensor, (0, sampling_rate - seg_audio_tensor.shape[1])
                    )

                ## Chop audio into further segments of 10 seconds if audio is longer than 10 seconds
                if seg_audio_tensor.shape[1] > sampling_rate * 10:
                    ceiling_len = (
                        seg_audio_tensor.shape[1] // (sampling_rate * 10)
                    ) * (sampling_rate * 10)
                    audio_segments = torch.tensor(
                        np.array(
                            [
                                seg_audio_tensor[:, i : i + sampling_rate * 10]
                                for i in range(0, ceiling_len, sampling_rate * 10)
                            ]
                        )
                    ).squeeze(
                        1
                    )  ## --> (N, 1600000)
                else:
                    audio_segments = seg_audio_tensor

                audio_segments = audio_segments.to(device)

                input_values = self.gender_processor(
                    audio_segments, sampling_rate=sampling_rate, return_tensors="pt"
                ).input_values.squeeze(
                    0
                )  ## --> (N, 1600000)
                input_values = input_values.to(device)

                with torch.no_grad():
                    result = self.gender_model(input_values).logits.softmax(dim=1)
                    gender_probs = result.mean(dim=0)

                prediction_idx = torch.argmax(gender_probs, dim=-1).item()
                gender_predictions.append(
                    Annotation(
                        start=seg.start,
                        end=seg.end,
                        labels=[
                            {
                                "gender_probs": gender_probs.tolist(),
                                "gender_pred": default_config["label_map"][
                                    prediction_idx
                                ],
                            }
                        ],
                    )
                )
            return gender_predictions

        if None in [self.gender_model, self.gender_processor]:
            self.gender_model, self.gender_processor = get_models()

        with (
            inputs["audio"] as input_audio,
            inputs["annotations"] as input_annotations,
            data_manager.create_data("AnnotationData") as annotation_data,
        ):
            with input_audio.open_audio("r") as audio_file:
                sampling_rate = 16000
                audio_array, _ = librosa.load(audio_file, sr=sampling_rate)
                for _, speaker_data in input_annotations:
                    with speaker_data as speaker_data:
                        gender_predictions = classify_segments(
                            audio_array, speaker_data.annotations, sampling_rate
                        )
                        annotation_data.annotations.extend(gender_predictions)

                self.update_callbacks(callbacks, progress=1.0)
                return {
                    "annotations": annotation_data,
                }
