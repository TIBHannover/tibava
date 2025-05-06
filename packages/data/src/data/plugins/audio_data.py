import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@DataManager.export("AudioData", analyser_pb2.AUDIO_DATA)
@dataclass(kw_only=True)
class AudioData(Data):
    type: str = field(default="AudioData")
    filename: str = None
    ext: str = None

    def load(self) -> None:
        super().load()
        data = self.load_dict("audio_data.yml")
        self.filename = data.get("filename")
        self.ext = data.get("ext")

    def save(self) -> None:
        super().save()

        self.save_dict(
            "audio_data.yml",
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

    def open_audio(self, mode="r"):
        assert self.check_fs(), "No fs register"
        return self.fs.open_file(f"audio.{self.ext}", mode)
