import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@dataclass(kw_only=True)
class ImageEmbedding(Data):
    image_id: str = None
    ref_id: str = None
    time: float = None
    delta_time: float = None
    embedding: npt.NDArray = None

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {
            **meta,
            "image_id": self.image_id,
            "ref_id": self.ref_id,
            "time": self.time,
            "delta_time": self.delta_time,
            "embedding": self.embedding.tolist(),
        }

    def to_save(self) -> dict:
        meta = super().to_dict()
        return {
            **meta,
            "image_id": self.image_id,
            "ref_id": self.ref_id,
            "time": self.time,
            "delta_time": self.delta_time,
        }


@DataManager.export("ImageEmbeddings", analyser_pb2.IMAGE_EMBEDDING_DATA)
@dataclass(kw_only=True)
class ImageEmbeddings(Data):
    type: str = field(default="ImageEmbeddings")
    embeddings: List[ImageEmbedding] = field(default_factory=list)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("image_embeddings_data.yml")
        self.embeddings = [ImageEmbedding(**x) for x in data.get("embeddings")]

        with self.fs.open_file("embeddings.npz", "r") as f:
            embeddings = np.load(f)
        if len(self.embeddings) != embeddings.shape[0]:
            logging.error(
                f"Data has invalid shape {len(self.embeddings)} vs. {embeddings.shape[0]}"
            )
            return

        for i in range(embeddings.shape[0]):
            self.embeddings[i].embedding = embeddings[i]

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        self.save_dict(
            "image_embeddings_data.yml",
            {"embeddings": [x.to_save() for x in self.embeddings]},
        )

        with self.fs.open_file("embeddings.npz", "w") as f:
            np.save(f, np.stack([x.embedding for x in self.embeddings], axis=0))

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "embeddings": [x.to_dict() for x in self.embeddings],
        }
