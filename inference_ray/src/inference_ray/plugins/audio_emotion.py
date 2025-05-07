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
    "save_dir": Path("/models/audio_emotion/"),
    "label_map": {
        0: "neutral",  # neu
        1: "angry",  # ang
        2: "happy",  # hap
        3: "sad",  # sad
    },
}

default_parameters = {}

requires = {
    "audio": AudioData,
    "annotations": ListData,
}

provides = {
    "annotations": AnnotationData,
}


@AnalyserPluginManager.export("audio_emotion")
class AudioEmotion(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

        self.emotion_model = None

        self.model_name = self.config.get("model", "audio_emotion_model")

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
        from speechbrain.inference.interfaces import foreign_class

        device = "cuda:0" if torch.cuda.is_available() else "cpu"

        def get_model() -> Tuple[Any, Any, Any]:
            run_opts = {"device": device}
            emotion_model = foreign_class(
                source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
                pymodule_file="custom_interface.py",
                classname="CustomEncoderWav2vec2Classifier",
                run_opts=run_opts,
                savedir=self.config.get("save_dir"),
            )
            return emotion_model

        def classify_segments(
            audio_array: np.ndarray,
            speaker_turns: List[Annotation],
            sampling_rate: int,
        ) -> Tuple[List[Annotation], List[Annotation]]:
            """
            Takes Speaker Diarization segments and classifies them into speech emotion categories.

            Args:
                audio_array (np.ndarray): Loaded audio series
                speaker_turns (List[Annotation]): List of speaker segments from ASR
                sampling_rate (int): Sampling rate of audio_array

            Returns:
                List[Annotation]: List of emotion predictions
            """
            emotion_predictions = []

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

                with torch.no_grad():
                    emotion_probs, _, _, _ = self.emotion_model.classify_batch(
                        audio_segments
                    )
                prediction_idx = torch.argmax(emotion_probs, dim=-1)[0].item()
                emotion_predictions.append(
                    Annotation(
                        start=seg.start,
                        end=seg.end,
                        labels=[
                            {
                                "emotion_probs": emotion_probs[0].tolist(),
                                "emotion_pred": default_config["label_map"][
                                    prediction_idx
                                ],
                            }
                        ],
                    )
                )
            return emotion_predictions

        if not self.emotion_model:
            self.emotion_model = get_model()

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
                        emotion_predictions = classify_segments(
                            audio_array, speaker_data.annotations, sampling_rate
                        )
                        annotation_data.annotations.extend(emotion_predictions)

                self.update_callbacks(callbacks, progress=1.0)
                return {
                    "annotations": annotation_data,
                }
