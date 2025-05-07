from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import VideoData, ListData

from data import DataManager, Data
from utils import VideoDecoder

import logging
from typing import Callable, Dict, List, Tuple


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "shot_scale_movement_classifier",
}

default_parameters = {
    "fps": 25,
    "seconds_per_prediction": 0.5,
}
# TODO maybe do predictions directly on shots

requires = {
    "video": VideoData,
}

provides = {
    "scale_probs": ListData,
    "movement_probs": ListData,
}


@AnalyserPluginManager.export("shot_scale_and_movement")
class ShotScaleAndMovement(
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
        import numpy as np
        import torch
        from torch import nn
        from torchvision.transforms import v2
        from transformers import (
            VideoMAEModel,
            VideoMAEImageProcessor,
            PreTrainedModel,
            VideoMAEConfig,
        )

        # Custom VideoMAE multi-task model definition for shot scale and movement classification
        class CustomVideoMAEConfig(VideoMAEConfig):
            def __init__(
                self,
                scale_label2id=None,
                scale_id2label=None,
                movement_label2id=None,
                movement_id2label=None,
                **kwargs,
            ):
                super().__init__(**kwargs)
                self.scale_label2id = (
                    scale_label2id if scale_label2id is not None else {}
                )
                self.scale_id2label = (
                    scale_id2label if scale_id2label is not None else {}
                )
                self.movement_label2id = (
                    movement_label2id if movement_label2id is not None else {}
                )
                self.movement_id2label = (
                    movement_id2label if movement_id2label is not None else {}
                )

        class CustomModel(PreTrainedModel):
            config_class = CustomVideoMAEConfig

            def __init__(
                self, config, scale_num_classes=None, movement_num_classes=None
            ):
                super().__init__(config)
                scale_num_classes = scale_num_classes or len(config.scale_label2id)
                movement_num_classes = movement_num_classes or len(
                    config.movement_label2id
                )
                self.vmae = VideoMAEModel(config)
                self.fc_norm = (
                    nn.LayerNorm(config.hidden_size)
                    if config.use_mean_pooling
                    else None
                )
                self.scale_cf = nn.Linear(config.hidden_size, scale_num_classes)
                self.movement_cf = nn.Linear(config.hidden_size, movement_num_classes)

            def forward(self, pixel_values, scale_labels=None, movement_labels=None):
                vmae_outputs = self.vmae(pixel_values)
                sequence_output = vmae_outputs[0]

                if self.fc_norm is not None:
                    sequence_output = self.fc_norm(sequence_output.mean(1))
                else:
                    sequence_output = sequence_output[:, 0]

                scale_logits = self.scale_cf(sequence_output)
                movement_logits = self.movement_cf(sequence_output)

                if scale_labels is not None and movement_labels is not None:
                    loss = nn.functional.cross_entropy(
                        scale_logits, scale_labels
                    ) + nn.functional.cross_entropy(movement_logits, movement_labels)
                    return {
                        "loss": loss,
                        "scale_logits": scale_logits,
                        "movement_logits": movement_logits,
                    }
                return {
                    "scale_logits": scale_logits,
                    "movement_logits": movement_logits,
                }

        device = "cuda" if torch.cuda.is_available() else "cpu"

        path = "gullalc/videomae-base-finetuned-kinetics-movieshots-multitask"
        model = CustomModel.from_pretrained(path)
        processor = VideoMAEImageProcessor.from_pretrained(path)
        model.eval()
        model.to(device)

        transform = v2.Compose(
            [
                v2.UniformTemporalSubsample(16),
                v2.Lambda(lambda x: x / 255.0),
                v2.Normalize(processor.image_mean, processor.image_std),
                v2.Resize((model.config.image_size, model.config.image_size)),
            ]
        )

        def get_probs(
            _batch: List[np.ndarray],
        ) -> Tuple[List[List[float]], List[List[float]]]:
            batch = torch.from_numpy(np.stack(_batch, axis=0))
            batch = batch.permute((0, 3, 1, 2)).unsqueeze(0)
            inputs = transform(batch).to(device)
            with torch.no_grad():
                outputs = model(inputs)
                scale_logits = outputs["scale_logits"]
                movement_logits = outputs["movement_logits"]
            return (
                torch.softmax(scale_logits, dim=1).tolist(),
                torch.softmax(movement_logits, dim=1).tolist(),
            )

        with inputs["video"] as video_data:
            with (
                video_data.open_video() as f_video,
                data_manager.create_data("ListData") as scale_probs_data,
                data_manager.create_data("ListData") as movement_probs_data,
            ):
                video_decoder = VideoDecoder(
                    path=f_video, extension=f".{video_data.ext}", fps=parameters["fps"]
                )

                # time batches (1 prediction per batch)
                _batch = []
                times = []
                scale_probs = []
                movement_probs = []
                time = 0
                for i, _frame in enumerate(video_decoder):
                    _batch.append(_frame.get("frame"))
                    if len(_batch) == int(
                        video_decoder.fps() * parameters["seconds_per_prediction"]
                    ):
                        times.append(time)
                        time = (i + 1) / video_decoder.fps()
                        scale_prob, movement_prob = get_probs(_batch)
                        scale_probs.extend(scale_prob)
                        movement_probs.extend(movement_prob)
                        _batch = []
                    self.update_callbacks(
                        callbacks,
                        progress=i / video_decoder.fps() / video_decoder.duration(),
                    )
                if len(_batch):
                    times.append(time)
                    scale_prob, movement_prob = get_probs(_batch)
                    scale_probs.extend(scale_prob)
                    movement_probs.extend(movement_prob)

                index = list(model.config.scale_id2label.values())
                logging.error(f"{times=}")
                for i, y in zip(index, zip(*scale_probs)):
                    with scale_probs_data.create_data(
                        "ScalarData", index=i
                    ) as scalar_data:
                        scalar_data.y = np.asarray(y)
                        scalar_data.time = times
                        scalar_data.delta_time = parameters["seconds_per_prediction"]

                index = list(model.config.movement_id2label.values())
                for i, y in zip(index, zip(*movement_probs)):
                    with movement_probs_data.create_data(
                        "ScalarData", index=i
                    ) as scalar_data:
                        scalar_data.y = np.asarray(y)
                        scalar_data.time = times
                        scalar_data.delta_time = parameters["seconds_per_prediction"]

            self.update_callbacks(callbacks, progress=1.0)
            return {
                "scale_probs": scale_probs_data,
                "movement_probs": movement_probs_data,
            }
