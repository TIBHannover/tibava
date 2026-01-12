import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np
from mava import GraphBuilder

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
    
    def compute_duration(self) -> float:
        return self.end - self.start
    
    def to_mava_dict(self) -> dict:
        return {
            **self.to_dict(),
            "duration": self.compute_duration()
        }


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
    
    def to_mava_dict(self) -> List[dict]:
        return [ann.to_mava_dict() for ann in self.annotations]
    
    
    def to_mava(self) -> bytes:
        mava_data = self.to_mava_dict()
        mava_mapping =  {
                    "series_description": "Annotation",
                    "value_description": "annotation",
                    "value_type": "string",
                    "value_prefix": "Annotation:: ",
                    "time_column": "start",
                    "value_column": "labels",
                    "duration_column": "duration"
                    }
        mava_graph = GraphBuilder()
        return mava_graph.add_mapped_data(mava_data, mava_mapping)
