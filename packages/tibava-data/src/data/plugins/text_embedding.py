import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@dataclass(kw_only=True)
class TextEmbedding(Data):
    text_id: int = None
    text: str = None
    embedding: npt.NDArray = None

    def to_dict(self) -> dict:
        return {
            "text_id": self.text_id,
            "text": self.text,
            "ref_id": self.ref_id,
            "embedding": self.embedding,
        }

    def to_save(self) -> dict:
        meta = super().to_dict()
        return {
            **meta,
            "text_id": self.text_id,
            "text": self.text,
            "ref_id": self.ref_id,
        }


@DataManager.export("TextEmbeddings", analyser_pb2.TEXT_EMBEDDING_DATA)
@dataclass(kw_only=True)
class TextEmbeddings(Data):
    type: str = field(default="TextEmbeddings")
    embeddings: List[TextEmbedding] = field(default_factory=list)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("text_embeddings_data.yml")
        self.embeddings = [TextEmbedding(**x) for x in data.get("embeddings")]

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
            "text_embeddings_data.yml",
            {"embeddings": [x.to_save() for x in self.embeddings]},
        )

        with self.fs.open_file("embeddings.npz", "w") as f:
            np.save(f, np.stack([x.embedding for x in self.embeddings], axis=0))

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "embeddings": [x.to_dict() for x in self.embeddings],
        }
