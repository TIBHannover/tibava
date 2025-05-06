import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@dataclass(kw_only=True)
class BboxData(Data):
    image_id: int = None
    ref_id: str = None
    time: float = None
    delta_time: float = field(default=None)
    x: int = None
    y: int = None
    w: int = None
    h: int = None
    det_score: float = 1.0

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {
            **meta,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "det_score": self.det_score,
            "time": self.time,
            "delta_time": self.delta_time,
            "ref_id": self.ref_id,
            "image_id": self.image_id,
        }


@DataManager.export("BboxesData", analyser_pb2.BBOXES_DATA)
@dataclass(kw_only=True)
class BboxesData(Data):
    type: str = field(default="BboxesData")
    bboxes: List[BboxData] = field(default_factory=list)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("bboxes_data.yml")
        self.bboxes = [BboxData(**x) for x in data.get("bboxes")]

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        self.save_dict(
            "bboxes_data.yml",
            {"bboxes": [box.to_dict() for box in self.bboxes]},
        )

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "bboxes": [box.to_dict() for box in self.bboxes],
        }
