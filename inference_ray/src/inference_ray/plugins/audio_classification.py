from typing import List, Tuple, Callable, Dict
from pathlib import Path
import sys

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager  # type: ignore
from data import AudioData, ListData, Annotation  # type: ignore

from data import DataManager, Data  # type: ignore

import logging

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "save_dir": Path("/models/audio_classification"),
}

default_parameters = {}

requires = {
    "audio": AudioData,
    "annotations": ListData,
}

provides = {"annotations": ListData}

"""
Additional files needed in data/models/audio_classification/
ontology.json: from fakenarratives repo
beats: git cloned and beats subfolder extracted from https://huggingface.co/spaces/fffiloni/SALMONN-7B-gradio/tree/677c0125de736ab92751385e1e8664cd03c2ce0d/beats (not available anymore)
    original repo/folder: https://github.com/microsoft/unilm/tree/master/beats
model from https://onedrive.live.com/?authkey=%21APLo1x9WFLcaKBI&id=6B83B49411CA81A7%2125955&cid=6B83B49411CA81A7&parId=root&parQt=sharedby&o=OneUp
"""


@AnalyserPluginManager.export("audio_classification")
class AudioClassification(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

        self.BEATs_model = None
        self.label_map = None

        self.model_name = self.config.get("model", "audio_classification_model")

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
        import json

        # beats has to be downloaded from huggingface and cannot be installed via pip
        sys.path.append("/models/audio_classification/")
        from beats.BEATs import BEATs, BEATsConfig  # type: ignore

        device = "cuda:0" if torch.cuda.is_available() else "cpu"

        def get_models() -> Tuple[BEATs, Dict[int, str]]:
            checkpoint = torch.load(
                self.config.get("save_dir")
                / "BEATs_iter3_plus_AS2M_finetuned_on_AS2M_cpt2.pt"
            )
            cfg = BEATsConfig(checkpoint["cfg"])
            BEATs_model = BEATs(cfg)
            BEATs_model.load_state_dict(checkpoint["model"])
            BEATs_model.to(device)
            BEATs_model.eval()

            with open(self.config.get("save_dir") / "ontology.json", "r") as f:
                data = json.load(f)

            idx_to_code = {v: k for k, v in checkpoint["label_dict"].items()}

            label_map = {}
            for entry in data:
                if entry["id"] in idx_to_code:
                    label_map[idx_to_code[entry["id"]]] = entry["name"]

            return BEATs_model, label_map

        def aggregate_probs(
            top3_label_probs: List[Tuple[List[str], List[float]]],
        ) -> List[Tuple[str, float]]:
            """
            Aggregates probabilities of each label across segments
            """
            label_probs = {}
            for labels, probs in top3_label_probs:
                for l, p in zip(labels, probs):
                    if l in label_probs:
                        label_probs[l] += p
                    else:
                        label_probs[l] = p

            total_prob = sum(label_probs.values())
            for l in label_probs:
                label_probs[l] /= total_prob

            top3_label_probs = sorted(
                label_probs.items(), key=lambda x: x[1], reverse=True
            )[:3]
            return top3_label_probs

        def classify_segments(
            audio_array: np.ndarray, segments: List[Annotation], sampling_rate: int
        ) -> List[Annotation]:
            """
            Takes Shot or Speaker Turn Segments and classifies them into audio categories

            Args:
                audio_path (Path): Path to audio file
                segments (List[Annotation]): List of segments with start and end times
                sampling_rate (int):

            Returns:
                List[Annotation]: List of segment predictions
            """
            segment_predictions = []

            for segment in segments:
                # slice audio of current segment
                segment_boundaries = librosa.time_to_samples(
                    np.array([segment.start, segment.end]), sr=sampling_rate
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

                padding_mask = (
                    torch.zeros(audio_segments.shape[0], audio_segments.shape[1])
                    .bool()
                    .to(device)
                )

                with torch.no_grad():
                    probs = self.BEATs_model.extract_features(
                        audio_segments, padding_mask=padding_mask
                    )[0]

                top3_label_probs = []
                for i, (top3_label_prob, top3_label_idx) in enumerate(
                    zip(*probs.topk(k=3))
                ):
                    top3_label_probs.append(
                        (
                            [
                                self.label_map[label_idx.item()]
                                for label_idx in top3_label_idx
                            ],
                            top3_label_prob.tolist(),
                        )
                    )

                top3_label_probs = aggregate_probs(top3_label_probs)
                segment_predictions.append(
                    Annotation(
                        start=segment.start,
                        end=segment.end,
                        labels=[
                            {
                                "label_pred_top3": [l for l, _ in top3_label_probs],
                                "label_prob_top3": [p for _, p in top3_label_probs],
                                "label_pred": top3_label_probs[0][0],
                            }
                        ],
                    )
                )

            return segment_predictions

        if None in [self.BEATs_model, self.label_map]:
            self.BEATs_model, self.label_map = get_models()

        with (
            inputs["audio"] as input_audio,
            inputs["annotations"] as input_annotations,
            data_manager.create_data("ListData") as output_data,
        ):
            with input_audio.open_audio("r") as audio_file:
                sampling_rate = 16000
                audio_array, _ = librosa.load(audio_file, sr=sampling_rate)
                if parameters.get("segment_type") == "Shot":
                    predictions = classify_segments(
                        audio_array, input_annotations, sampling_rate
                    )

                    with output_data.create_data("AnnotationData") as ann_data:
                        ann_data.annotations.extend(predictions)
                        ann_data.name = "Shot"

                elif parameters.get("segment_type") == "Speaker":
                    for _, speaker_data in input_annotations:
                        with speaker_data as speaker_data:
                            predictions = classify_segments(
                                audio_array, speaker_data.annotations, sampling_rate
                            )

                            with output_data.create_data("AnnotationData") as ann_data:
                                ann_data.annotations.extend(predictions)
                                ann_data.name = speaker_data.name
                else:
                    raise NotImplementedError(
                        f"Unknown segment type: {parameters.get('segment_type')}"
                    )

                self.update_callbacks(callbacks, progress=1.0)
                # TODO maybe separate shot and speaker annotations in two entries
                return {
                    "annotations": output_data,
                }
