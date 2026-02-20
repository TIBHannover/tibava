import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@dataclass(kw_only=True)
class Annotation:
    start: float
    end: float
    labels: list

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "labels": self.labels}


@DataManager.export("AnnotationData", analyser_pb2.ANNOTATION_DATA)
@dataclass(kw_only=True)
class AnnotationData(Data):
    type: str = field(default="AnnotationData")
    annotations: List[Annotation] = field(default_factory=list)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("annotation_data.yml")
        self.annotations = [Annotation(**x) for x in data.get("annotations")]

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        self.save_dict(
            "annotation_data.yml",
            {"annotations": [ann.to_dict() for ann in self.annotations]},
        )

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "annotations": [ann.to_dict() for ann in self.annotations],
        }
