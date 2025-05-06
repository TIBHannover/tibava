from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import ScalarData, VideoData
from utils import VideoDecoder
import numpy as np
from data import DataManager, Data

from typing import Callable, Optional, Dict
import logging

default_config = {"data_dir": "/data/"}


default_parameters = {
    "fps": 5,
    "normalize": True,
}

requires = {
    "video": VideoData,
}

provides = {
    "brightness": ScalarData,
}


@AnalyserPluginManager.export("color_brightness_analyser")
class ColorBrightnessAnalyser(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.5",
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
        import cv2

        with (
            inputs["video"] as input_data,
            data_manager.create_data("ScalarData") as output_data,
        ):
            with input_data.open_video() as f_video:
                video_decoder = VideoDecoder(
                    f_video,
                    max_dimension=parameters.get("max_resolution"),
                    fps=parameters.get("fps"),
                    extension=f".{input_data.ext}",
                )

                values = []
                time = []
                num_frames = video_decoder.duration() * video_decoder.fps()
                for i, frame in enumerate(video_decoder):
                    self.update_callbacks(callbacks, progress=i / num_frames)
                    image = frame["frame"]
                    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV) / 255
                    value = np.mean(hsv[:, :, 2])
                    values.append(value)
                    time.append(i / parameters.get("fps"))

            y = np.stack(values)
            if parameters.get("normalize"):
                y = (y - np.min(y)) / (np.max(y) - np.min(y))

            self.update_callbacks(callbacks, progress=1.0)

            output_data.y = y
            output_data.time = time
            output_data.delta_time = 1 / parameters.get("fps")
            return {"brightness": output_data}
