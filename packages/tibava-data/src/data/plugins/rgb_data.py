import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@DataManager.export("RGBData", analyser_pb2.RGB_DATA)
@dataclass(kw_only=True)
class RGBData(Data):
    type: str = field(default="RGBData")
    colors: npt.NDArray = None
    time: npt.NDArray = None
    delta_time: float = field(default=None)

    def load(self) -> None:
        super().load()
        data = self.load_dict("rgb_data.yml")
        self.delta_time = data.get("delta_time")

        with self.fs.open_file("colors.npz", "r") as f:
            self.colors = np.load(f)

        with self.fs.open_file("time.npz", "r") as f:
            self.time = np.load(f)

    def save(self) -> None:
        super().save()

        self.save_dict(
            "rgb_data.yml",
            {
                "delta_time": self.delta_time,
            },
        )
        with self.fs.open_file("colors.npz", "w") as f:
            np.save(f, self.colors)

        with self.fs.open_file("time.npz", "w") as f:
            np.save(f, self.time)

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "colors": self.colors.tolist(),
            "time": self.time.tolist(),
            "delta_time": self.delta_time,
        }
