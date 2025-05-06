from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager

from utils import VideoDecoder
from data import Shot, ShotsData, VideoData

# from inference import InferenceServer
from data import DataManager, Data

from typing import Callable, Optional, Dict

import numpy as np
import logging

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "transnet",
    "model_device": "cpu",
    "model_file": "/models/transnet_shotdetection/transnet.pt",
}

default_parameters = {"threshold": 0.5}

requires = {
    "video": VideoData,
}

provides = {
    "shots": ShotsData,
}


@AnalyserPluginManager.export("transnet_shotdetection")
class TransnetShotdetection(
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
        self.model_path = self.config.get("model_path")

    def predict_frames(self, frames: np.ndarray, callbacks):
        import torch

        def input_iterator():
            # return windows of size 100 where the first/last 25 frames are from the previous/next batch
            # the first and last window must be padded by copies of the first and last frame of the video
            no_padded_frames_start = 25
            no_padded_frames_end = (
                25 + 50 - (len(frames) % 50 if len(frames) % 50 != 0 else 50)
            )  # 25 - 74

            start_frame = np.expand_dims(frames[0], 0)
            end_frame = np.expand_dims(frames[-1], 0)
            padded_inputs = np.concatenate(
                [start_frame] * no_padded_frames_start
                + [frames]
                + [end_frame] * no_padded_frames_end,
                0,
            )

            ptr = 0
            while ptr + 100 <= len(padded_inputs):
                out = padded_inputs[ptr : ptr + 100]
                progress = ptr / len(padded_inputs)
                ptr += 50
                yield progress, out[np.newaxis]

        predictions = []
        # max_iter = len(input_iterator())
        for progress, inp in input_iterator():
            # (131362, 27, 48, 3)
            self.update_callbacks(callbacks, progress=progress)

            with torch.no_grad(), torch.cuda.amp.autocast():
                raw_result = self.model(torch.from_numpy(inp).to(self.device))
            single_frame_pred = raw_result[0].cpu().detach().numpy()
            all_frames_pred = raw_result[1].cpu().detach().numpy()
            # result = self.server({"data": inp}, ["single_frame_pred", "all_frames_pred"])

            # if result is not None:
            #     single_frame_pred = result.get(f"single_frame_pred")
            #     all_frames_pred = result.get(f"all_frames_pred")

            predictions.append(
                (single_frame_pred[0, 25:75, 0], all_frames_pred[0, 25:75, 0])
            )

        single_frame_pred = np.concatenate([single_ for single_, all_ in predictions])
        all_frames_pred = np.concatenate([all_ for single_, all_ in predictions])

        return (
            single_frame_pred[: len(frames)],
            all_frames_pred[: len(frames)],
        )  # remove extra padded frames

    def predictions_to_scenes(self, predictions: np.ndarray, threshold: float = 0.5):
        predictions = (predictions > threshold).astype(np.uint8)

        scenes = []
        t, t_prev, start = -1, 0, 0
        for i, t in enumerate(predictions):
            if t_prev == 1 and t == 0:
                start = i
            if t_prev == 0 and t == 1 and i != 0:
                scenes.append([start, i])
            t_prev = t
        if t == 0:
            scenes.append([start, i])

        # just fix if all predictions are 1
        if len(scenes) == 0:
            return np.array([[0, len(predictions) - 1]], dtype=np.int32)

        return np.array(scenes, dtype=np.int32)

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

        self.update_callbacks(callbacks, progress=0.0)
        with (
            inputs["video"] as input_data,
            data_manager.create_data("ShotsData") as output_data,
        ):
            frames = []
            with input_data.open_video() as f_video:
                video_decoder = VideoDecoder(
                    path=f_video,
                    max_dimension=[27, 48],
                    extension=f".{input_data.ext}",
                )
                for x in video_decoder:
                    frames.append(x.get("frame"))

                frames = np.stack(frames, axis=0)

                video_decoder.fps

                video = frames.reshape([-1, 27, 48, 3])

                prediction, _ = self.predict_frames(video, callbacks)

                shot_list = self.predictions_to_scenes(
                    prediction, parameters.get("threshold")
                )

                output_data.shots = [
                    Shot(
                        start=x[0].item() / video_decoder.fps(),
                        end=x[1].item() / video_decoder.fps(),
                    )
                    for x in shot_list
                ]

                self.update_callbacks(callbacks, progress=1.0)

                return {"shots": output_data}
