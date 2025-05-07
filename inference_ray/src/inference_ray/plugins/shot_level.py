from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import ScalarData, VideoData, ListData

from data import DataManager, Data
from utils import VideoDecoder

import logging
from typing import Callable, Dict, List


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "shot_level_classifier",
}

default_parameters = {
    "fps": 2,
    "batch_size": 32,
}

requires = {
    "video": VideoData,
}

provides = {
    "probs": ListData,
}


@AnalyserPluginManager.export("shot_level")
class ShotLevel(
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
        from torchvision.transforms import v2
        from transformers import AutoModelForImageClassification

        device = "cuda" if torch.cuda.is_available() else "cpu"

        transform = v2.Compose(
            [
                v2.Resize(384, antialias=True),
                v2.CenterCrop((384, 384)),
                v2.ToDtype(torch.float32, scale=True),
                v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )

        model = AutoModelForImageClassification.from_pretrained(
            "gullalc/convnextv2-base-22k-224-cinescale-level"
        )
        model.to(device)
        model.eval()

        def get_probs(_batch: List[np.ndarray]) -> List[List[float]]:
            batch = torch.from_numpy(np.stack(_batch, axis=0))
            batch = batch.permute((0, 3, 1, 2))
            inputs = transform(batch).to(device)
            with torch.no_grad():
                outputs = model(inputs).logits
            return torch.softmax(outputs, dim=1).tolist()

        with inputs["video"] as video_data:
            with (
                video_data.open_video() as f_video,
                data_manager.create_data("ListData") as probs_data,
            ):
                video_decoder = VideoDecoder(
                    path=f_video, extension=f".{video_data.ext}", fps=parameters["fps"]
                )

                _batch = []
                times = []
                probs = []
                for i, _frame in enumerate(video_decoder):
                    _batch.append(_frame.get("frame"))
                    times.append(i / video_decoder.fps())
                    if len(_batch) == parameters["batch_size"]:
                        probs.extend(get_probs(_batch))
                        _batch = []
                    self.update_callbacks(
                        callbacks,
                        progress=i / video_decoder.fps() / video_decoder.duration(),
                    )
                if len(_batch):
                    probs.extend(get_probs(_batch))

                index = list(model.config.id2label.values())
                for i, y in zip(index, zip(*probs)):
                    with probs_data.create_data("ScalarData", index=i) as scalar_data:
                        scalar_data.y = np.asarray(y)
                        scalar_data.time = times
                        scalar_data.delta_time = 1 / parameters.get("fps")

            self.update_callbacks(callbacks, progress=1.0)
            return {"probs": probs_data}
