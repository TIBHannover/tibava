from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import VideoData, ListData, RGBData
from utils import VideoDecoder
from data import DataManager, Data

import logging
from typing import Callable, Optional, Dict
import numpy as np

default_config = {"data_dir": "/data/"}


default_parameters = {
    "k": 1,
    "fps": 5,
    "max_iter": 10,
    "max_resolution": 48,
}

requires = {
    "video": VideoData,
}

provides = {
    "colors": ListData,
}


@AnalyserPluginManager.export("color_analyser")
class ColorAnalyser(
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
        from sklearn.cluster import KMeans

        with (
            inputs["video"] as input_data,
            data_manager.create_data("ListData") as output_data,
        ):
            kcolors = []
            time = []
            with input_data.open_video() as f_video:
                video_decoder = VideoDecoder(
                    f_video,
                    max_dimension=parameters.get("max_resolution"),
                    fps=parameters.get("fps"),
                    extension=f".{input_data.ext}",
                )

                num_frames = video_decoder.duration() * video_decoder.fps()
                for i, frame in enumerate(video_decoder):
                    self.update_callbacks(callbacks, progress=i / num_frames)
                    image = frame["frame"]
                    image = image.reshape((image.shape[0] * image.shape[1], 3))
                    cls = KMeans(
                        n_clusters=parameters.get("k"),
                        max_iter=parameters.get("max_iter"),
                    )
                    labels = cls.fit_predict(image)
                    colors = cls.cluster_centers_.tolist()
                    kcolors.append(
                        np.asarray([colors[x] for x in np.argsort(np.bincount(labels))])
                    )
                    time.append(i / parameters.get("fps"))

            kcolors = np.stack(kcolors, axis=0)
            for colors in zip(*kcolors):
                with output_data.create_data("RGBData") as color_data:
                    color_data.colors = np.asarray(colors) / 255
                    color_data.time = np.asarray(time)
                    color_data.delta_time = 1 / parameters.get("fps")

            self.update_callbacks(callbacks, progress=1.0)
            return {"colors": output_data}
