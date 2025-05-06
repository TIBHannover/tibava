import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@DataManager.export("HistData", analyser_pb2.HIST_DATA)
@dataclass(kw_only=True)
class HistData(Data):
    type: str = field(default="HistData")
    hist: npt.NDArray = None
    time: npt.NDArray = None
    delta_time: float = field(default=None)

    def load(self) -> None:
        super().load()
        data = self.load_dict("hist_data.yml")
        self.delta_time = data.get("delta_time")

        with self.fs.open_file("hist.npz", "r") as f:
            self.hist = np.load(f)

        with self.fs.open_file("time.npz", "r") as f:
            self.time = np.load(f)

    def save(self) -> None:
        super().save()

        self.save_dict(
            "hist_data.yml",
            {
                "delta_time": self.delta_time,
            },
        )
        with self.fs.open_file("hist.npz", "w") as f:
            np.save(f, self.hist)

        with self.fs.open_file("time.npz", "w") as f:
            np.save(f, self.time)

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "hist": self.hist.tolist(),
            "time": self.time.tolist(),
            "delta_time": self.delta_time,
        }
