import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@DataManager.export("ScalarData", analyser_pb2.SCALAR_DATA)
@dataclass(kw_only=True)
class ScalarData(Data):
    type: str = field(default="ScalarData")
    y: npt.NDArray = None
    time: npt.NDArray = None
    delta_time: float = field(default=None)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("scalar_data.yml")
        self.delta_time = data.get("delta_time")

        with self.fs.open_file("y.npz", "r") as f:
            self.y = np.load(f)

        with self.fs.open_file("time.npz", "r") as f:
            self.time = np.load(f)

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        self.save_dict(
            "scalar_data.yml",
            {
                "delta_time": self.delta_time,
            },
        )
        with self.fs.open_file("y.npz", "w") as f:
            np.save(f, self.y)

        with self.fs.open_file("time.npz", "w") as f:
            np.save(f, self.time)

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "y": self.y.tolist(),
            "time": self.time.tolist(),
            "delta_time": self.delta_time,
        }
