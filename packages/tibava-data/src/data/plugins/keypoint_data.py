import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@dataclass(kw_only=True)
class KpsData(Data):
    image_id: int = None
    ref_id: str = None
    time: float = None
    delta_time: float = field(default=None)
    x: List[float] = None
    y: List[float] = None

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {
            **meta,
            "x": self.x,
            "y": self.y,
            "time": self.time,
            "delta_time": self.delta_time,
            "ref_id": self.ref_id,
        }


@DataManager.export("KpssData", analyser_pb2.KPSS_DATA)
@dataclass(kw_only=True)
class KpssData(Data):
    type: str = field(default="KpssData")
    kpss: List[KpsData] = field(default_factory=list)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("kpss_data.yml")
        self.kpss = [KpsData(**x) for x in data.get("kpss")]

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        self.save_dict("kpss_data.yml", {"kpss": [x.to_dict() for x in self.kpss]})

    def to_dict(self) -> dict:
        return {**super().to_dict(), "kpss": [x.to_dict() for x in self.kpss]}
