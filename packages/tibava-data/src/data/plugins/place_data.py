import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@dataclass(kw_only=True)
class PlaceData(Data):
    time: float = None
    place365prob: float = None
    place365class: str = "None"
    place16prob: float = None
    place16class: str = "None"
    place3prob: float = None
    place3class: str = "None"

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {
            **meta,
            "time": self.time,
            # "place365prob": self.place365prob.tolist(),
            # "place16prob": self.place16prob.tolist(),
            # "place3prob": self.place3prob.tolist(),
            "place365class": self.place365class,
            "place16class": self.place16class,
            "place3class": self.place3class,
        }


@DataManager.export("PlacesData", analyser_pb2.PLACES_DATA)
@dataclass(kw_only=True)
class PlacesData(Data):
    type: str = field(default="PlacesData")
    places: List[PlaceData] = field(default_factory=list)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("places_data.yml")
        self.places = [PlaceData(**x) for x in data.get("places")]

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        self.save_dict(
            "places_data.yml",
            {"places": [place.to_dict() for place in self.places]},
        )

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "places": [place.to_dict() for place in self.places],
        }
