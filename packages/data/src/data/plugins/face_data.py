import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@dataclass(kw_only=True)
class FaceData(Data):
    pass


@DataManager.export("FacesData", analyser_pb2.FACES_DATA)
@dataclass(kw_only=True)
class FacesData(Data):
    type: str = field(default="FacesData")
    faces: List[FaceData] = field(default_factory=list)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("faces_data.yml")
        self.faces = [FaceData(**x) for x in data.get("faces")]

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        self.save_dict(
            "faces_data.yml",
            {"faces": [face.to_dict() for face in self.faces]},
        )

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "faces": [face.to_dict() for face in self.faces],
        }
