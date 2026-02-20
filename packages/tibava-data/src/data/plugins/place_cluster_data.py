import logging
from typing import List
from dataclasses import dataclass, field

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from .place_data import PlacesData, PlaceData
from .image_data import ImagesData, ImageData
from interface import analyser_pb2
from .image_embedding import ImageEmbedding
from .cluster_data import Cluster


@DataManager.export("PlaceClusterData", analyser_pb2.PLACE_CLUSTER_DATA)
@dataclass(kw_only=True)
class PlaceClusterData(Data):
    type: str = field(default="PlaceClusterData")
    clusters: List[Cluster] = field(default_factory=list)
    places: PlacesData = field(default_factory=PlacesData)
    images: ImagesData = field(default_factory=ImagesData)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("place_cluster_data.yml")
        self.clusters = [Cluster(**x) for x in data.get("cluster")]

        self.places = [PlaceData(**x) for x in data.get("places")]
        self.images = [ImageData(**x) for x in data.get("images")]

        with self.fs.open_file("place_cluster_embeddings.npz", "r") as f:
            embeddings = np.load(f)

        cluster_feature_lut = data.get("cluster_feature_lut")

        for i in range(len(self.clusters)):
            self.clusters[i].embedding_repr = embeddings[
                cluster_feature_lut[i][0] : cluster_feature_lut[i][1]
            ]

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        cluster_feature_lut = {}

        i = 0
        for j, cluster in enumerate(self.clusters):
            cluster_feature_lut[j] = (i, i + len(cluster.embedding_repr))
            i += len(cluster.embedding_repr)

        self.save_dict(
            "place_cluster_data.yml",
            {
                "cluster": [c.to_dict() for c in self.clusters],
                "cluster_feature_lut": cluster_feature_lut,
                "places": [place.to_dict() for place in self.places.places],
                "images": [image.to_dict() for image in self.images.images],
            },
        )

        with self.fs.open_file("place_cluster_embeddings.npz", "w") as f:
            np.save(
                f, np.concatenate([x.embedding_repr for x in self.clusters], axis=0)
            )

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "cluster": [c.to_dict() for c in self.clusters],
            "places": [place.to_dict() for place in self.places],
            "images": [image.to_dict() for image in self.images],
        }
