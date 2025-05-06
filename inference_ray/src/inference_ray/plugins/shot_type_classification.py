from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from utils import VideoDecoder, image_pad
from data import ListData, ScalarData, VideoData, ListData

from data import DataManager, Data

from typing import Callable, Optional, Dict

import numpy as np
import logging


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "shot_type_classifier",
    "model_device": "cpu",
    "model_file": "/models/shot_type_classification/shot_type_classifier_e9-s3199_cpu.pt",
    "image_resolution": 224,
}

default_parameters = {"fps": 5}

requires = {
    "video": VideoData,
}

provides = {
    "probs": ListData,
}


@AnalyserPluginManager.export("shot_type_classifier")
class ShotTypeClassifier(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        self.image_resolution = self.config["image_resolution"]

        self.model = None
        self.model_path = self.config.get("model_path")

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.model is None:
            self.model = torch.jit.load(
                self.model_path, map_location=torch.device(device)
            )
            self.device = device

        with (
            inputs["video"] as input_data,
            data_manager.create_data("ListData") as output_data,
        ):
            with input_data.open_video() as f_video:
                video_decoder = VideoDecoder(
                    path=f_video,
                    max_dimension=self.image_resolution,
                    fps=parameters.get("fps"),
                    extension=f".{input_data.ext}",
                )

                # video_decoder.fps

                predictions = []
                time = []

                num_frames = video_decoder.duration() * video_decoder.fps()
                for i, frame in enumerate(video_decoder):
                    self.update_callbacks(callbacks, progress=i / num_frames)
                    frame = image_pad(frame["frame"])

                    with torch.no_grad(), torch.cuda.amp.autocast():
                        frame = torch.from_numpy(frame).to(self.device)
                        raw_result = self.model(frame)
                    result = raw_result.cpu().detach().numpy()
                    # result = self.server({"data": np.expand_dims(frame, 0)}, ["prob"])
                    # if result is not None:
                    predictions.append(np.squeeze(result).tolist())
                    time.append(i / parameters.get("fps"))
                # predictions = zip(*predictions)
                index = ["p_ECU", "p_CU", "p_MS", "p_FS", "p_LS"]
                for i, y in zip(index, zip(*predictions)):
                    with output_data.create_data("ScalarData", index=i) as scalar_data:
                        scalar_data.y = np.asarray(y)
                        scalar_data.time = time
                        scalar_data.delta_time = 1 / parameters.get("fps")
                # probs = ListData(
                #     data=[
                #         ScalarData(y=np.asarray(y), time=time, delta_time=1 / parameters.get("fps"))
                #         for y in zip(*predictions)
                #     ],
                #     index=["p_ECU", "p_CU", "p_MS", "p_FS", "p_LS"],
                # )

                # predictions: list(np.array) in form of [(p_ECU, p_CU, p_MS, p_FS, p_LS), ...] * #frames
                # times: list in form [0 / fps, 1 / fps, ..., #frames/fps]

                self.update_callbacks(callbacks, progress=1.0)
                return {"probs": output_data}
