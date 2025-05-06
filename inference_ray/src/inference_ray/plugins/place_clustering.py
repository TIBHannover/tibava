from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager

from data import ImageEmbeddings, PlaceClusterData, Cluster, PlacesData

import logging
import numpy as np
from data import DataManager, Data

from typing import Callable, Optional, Dict


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {
    "min_threshold": None,
    "max_threshold": None,
    "cluster_threshold": 0.25,
}

requires = {"embeddings": ImageEmbeddings}

provides = {
    "place_cluster_data": PlaceClusterData,
}


@AnalyserPluginManager.export("place_clustering")
class PlaceClustering(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        self.host = self.config["host"]
        self.port = self.config["port"]

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        from scipy.cluster.hierarchy import fclusterdata

        with (
            inputs["embeddings"] as place_embeddings,
            inputs["places"] as places,
            data_manager.create_data("PlaceClusterData") as output_data,
        ):
            embeddings = np.asarray(
                [em.embedding for em in place_embeddings.embeddings]
            )
            place_ids = [f.id for f in places.places]

            metric = "cosine"
            result = fclusterdata(
                X=embeddings,
                t=parameters.get("cluster_threshold"),
                criterion="distance",
                metric=metric,
            )

            # result format: list of cluster ids [1 2 1 3]

            clustered_embeddings = [[] for _ in np.unique(result)]
            output_data.clusters = [Cluster() for _ in np.unique(result)]

            for c in output_data.clusters:
                c.object_refs = []

            # sort place refs into clusters
            for id, cluster_id in enumerate(result):
                output_data.clusters[cluster_id - 1].object_refs.append(place_ids[id])
                clustered_embeddings[cluster_id - 1].append(embeddings[id])

            # compute mean embedding for each cluster
            for id, embedding_cluster in enumerate(clustered_embeddings):
                converted_clusters = [x for x in embedding_cluster]
                output_data.clusters[id].embedding_repr = converted_clusters

            # sort clusters and embeddings together by cluster length
            output_data.clusters = sorted(
                output_data.clusters,
                key=lambda cluster: (len(cluster.object_refs)),
                reverse=True,
            )
            output_data.places = places

            return {"place_cluster_data": output_data}
