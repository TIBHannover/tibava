from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import AudioData, VideoData, DataManager, Data


from typing import Callable, Optional, Dict

default_config = {"data_dir": "/data/"}


default_parameters = {
    "sample_rate": 48000,
    "sample_format": "pcm_s16le",
    "layout": "mono",
    "extension": "wav",
}

requires = {
    "video": VideoData,
}

provides = {
    "audio": AudioData,
}


@AnalyserPluginManager.export("video_to_audio")
class VideoToAudio(
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
        import av

        with (
            inputs["video"] as input_data,
            data_manager.create_data("AudioData") as output_data,
        ):
            output_data.ext = parameters.get("extension")

            with (
                input_data.open_video() as f_video,
                output_data.open_audio("w") as f_audio,
            ):
                with av.open(
                    f_video, format=input_data.ext, metadata_errors="ignore"
                ) as in_container:
                    in_stream = in_container.streams.audio[0]
                    with av.open(f_audio, "w", output_data.ext) as out_container:
                        out_stream = out_container.add_stream(
                            parameters.get("sample_format"),
                            rate=parameters.get("sample_rate"),
                            layout=parameters.get("layout"),
                        )
                        for frame in in_container.decode(in_stream):
                            for packet in out_stream.encode(frame):
                                out_container.mux(packet)

            return {"audio": output_data}
