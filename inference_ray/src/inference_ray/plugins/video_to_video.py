from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import VideoData
from data import DataManager, Data

from typing import Callable, Optional, Dict

default_config = {"data_dir": "/data/"}


default_parameters = {}

requires = {
    "video": VideoData,
}

provides = {
    "video": VideoData,
}


@AnalyserPluginManager.export("video_to_video")
class VideoToVideo(
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
        import ffmpeg

        output_data = VideoData(ext="mp4", data_dir=self.config.get("data_dir"))

        video = ffmpeg.input(inputs["video"].path)

        stream = ffmpeg.output(
            video.video,
            video.audio,
            output_data.path,
            preset="faster",
            ac=2,
            vcodec="libx264",
            acodec="aac",
        )

        ffmpeg.run(stream)

        self.update_callbacks(callbacks, progress=1.0)
        return {"audio": output_data}
