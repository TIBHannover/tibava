import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@dataclass(kw_only=True)
class Shot:
    start: float
    end: float

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end}


@DataManager.export("ShotsData", analyser_pb2.SHOTS_DATA)
@dataclass(kw_only=True)
class ShotsData(Data):
    type: str = field(default="ShotsData")
    shots: List[Shot] = field(default_factory=list)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("shots_data.yml")
        self.shots = [Shot(**x) for x in data.get("shots")]

    def __iter__(self):
        yield from self.shots

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        self.save_dict(
            "shots_data.yml",
            {
                "shots": [x.to_dict() for x in self.shots],
            },
        )

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "shots": [x.to_dict() for x in self.shots],
        }
