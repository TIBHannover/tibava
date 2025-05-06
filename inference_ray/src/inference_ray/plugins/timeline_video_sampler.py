import logging
import sys

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import (
    VideoData,
    ShotsData,
    ImagesData,
)
from data import DataManager, Data

from typing import Callable, Optional, Dict, Union

default_config = {}

timeline_video_sampler_parameters = {
    "middle_frame": True,
    "start_frame": False,
    "end_frame": False,
}

timeline_video_sampler_requires = {
    "input": Union[VideoData, ImagesData],
    "shots": ShotsData,
}

timeline_video_sampler_provides = {
    "output": ImagesData,
}


@AnalyserPluginManager.export("timeline_video_sampler")
class TimelineVideoSampler(
    AnalyserPlugin,
    config=default_config,
    parameters=timeline_video_sampler_parameters,
    version="0.5",
    requires=timeline_video_sampler_requires,
    provides=timeline_video_sampler_provides,
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

        with (
            inputs["input"] as input_data,
            inputs["shots"] as shots_data,
            data_manager.create_data("ImagesData") as output_data,
        ):
            shot_iter = iter(shots_data)

            current_shot = next(shot_iter, None)
            if current_shot is None:
                return {"output": output_data}

            middle_time = (
                current_shot.end - current_shot.start
            ) / 2 + current_shot.start
            middle_closest = sys.float_info.max
            middle_frame = None
            start_closest = sys.float_info.max
            start_frame = None
            end_closest = sys.float_info.max
            end_frame = None

            result_images = []
            with input_data() as input_iterator:
                for frame in input_iterator:
                    time = frame["time"]

                    if (
                        parameters.get("start_frame")
                        and time >= current_shot.start
                        and abs(current_shot.start - time) < start_closest
                    ):
                        start_closest = abs(current_shot.start - time)
                        start_frame = frame

                    if (
                        parameters.get("end_frame")
                        and time <= current_shot.end
                        and abs(current_shot.end - time) < end_closest
                    ):
                        end_closest = abs(current_shot.end - time)
                        end_frame = frame

                    if (
                        parameters.get("middle_frame")
                        and abs(middle_time - time) < middle_closest
                    ):
                        middle_closest = abs(middle_time - time)
                        middle_frame = frame

                    if time >= current_shot.end:
                        if start_frame:
                            result_images.append(start_frame)
                            start_frame = None
                        if middle_frame:
                            result_images.append(middle_frame)
                            middle_frame = None
                        if end_frame:
                            result_images.append(end_frame)
                            end_frame = None

                        current_shot = next(shot_iter, None)
                        if current_shot is None:
                            break

                        middle_time = (
                            current_shot.end - current_shot.start
                        ) / 2 + current_shot.start
                        middle_closest = sys.float_info.max
                        start_closest = sys.float_info.max
                        end_closest = sys.float_info.max

                if start_frame:
                    result_images.append(start_frame)
                if middle_frame:
                    result_images.append(middle_frame)
                if end_frame:
                    result_images.append(end_frame)

            for image in result_images:

                output_data.save_image(
                    image.get("frame"),
                    ext="jpg",
                    time=image.get("time"),
                    delta_time=1 / image.get("delta_time"),
                )

            return {"output": output_data}
