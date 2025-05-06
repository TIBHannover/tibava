import logging

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2
from dataclasses import dataclass, field, fields
from collections.abc import Iterable
from utils import VideoDecoder


@DataManager.export("VideoData", analyser_pb2.VIDEO_DATA)
@dataclass(kw_only=True)
class VideoData(Data):
    type: str = field(default="VideoData")
    filename: str = None
    ext: str = None

    def load(self) -> None:
        super().load()
        data = self.load_dict("video_data.yml")
        self.filename = data.get("filename")
        self.ext = data.get("ext")

    def save(self) -> None:
        super().save()

        self.save_dict(
            "video_data.yml",
            {
                "filename": self.filename,
                "ext": self.ext,
            },
        )

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "filename": self.filename,
            "ext": self.ext,
        }

    def __call__(self, fps: float = None, **kwargs) -> "VideoIterator":
        return VideoIterator(self, fps=fps)

    def open_video(self, mode="r"):
        assert self.check_fs(), "No fs register"
        return self.fs.open_file(f"video.{self.ext}", mode)

    def load_file_from_stream(self, data_stream: Iterable) -> None:

        assert self.check_fs(), "No fs register"
        assert self.fs.mode == "w", "Fs is not writeable"

        data_stream = iter(data_stream)
        first_pkg = next(data_stream)

        self.ext = first_pkg.ext
        self.filename = first_pkg.filename
        with self.open_video("w") as f:
            f.write(first_pkg.data_encoded)
            for x in data_stream:
                f.write(x.data_encoded)


class VideoIterator:
    def __init__(self, data: VideoData, fps: float = None):
        self.data = data
        self.fps = fps
        self.video_file = None
        self.video_decoder = None

    def __enter__(self):
        self.video_file = self.data.open_video("r")

        self.video_decoder = VideoDecoder(
            self.video_file, fps=self.fps, extension=f".{self.data.ext}"
        )
        return self.video_decoder

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.video_file is not None:
            self.video_file.close()
