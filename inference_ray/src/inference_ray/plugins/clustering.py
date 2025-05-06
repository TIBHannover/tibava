import logging
import numpy as np
from typing import Callable, Optional, Dict

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import DataManager, Data, ImageEmbeddings, ClusterData, Cluster


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {
    "cluster_threshold": 0.5,
    "max_samples_per_cluster": 30,
}

requires = {
    "embeddings": ImageEmbeddings,
}

provides = {
    "cluster_data": ClusterData,
}


@AnalyserPluginManager.export("clustering")
class Clustering(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1.2",
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
            inputs["embeddings"] as embeddings,
            data_manager.create_data("ClusterData") as output_data,
        ):
            np_embeddings = np.squeeze(
                np.asarray([em.embedding for em in embeddings.embeddings])
            )

            metric = "cosine"
            result = fclusterdata(
                X=np_embeddings,
                t=parameters.get("cluster_threshold"),
                criterion="distance",
                metric=metric,
            )
            # result format: list of cluster ids [1 2 1 3]
            clusters = []
            for x in np.unique(result):
                ids = np.where(result == x)[0]

                cluster_size = len(ids)

                logging.error(f"{cluster_size} {ids}")
                ids_ids = np.linspace(
                    0,
                    cluster_size - 1,
                    min(cluster_size, parameters.get("max_samples_per_cluster")),
                )
                logging.error(f"a {ids_ids}")
                ids_ids = [round(idx) for idx in ids_ids]
                logging.error(f"b {ids_ids}")

                logging.error(f"old {ids}")
                sample_ids = ids[ids_ids]
                logging.error(f"new {ids}")

                clusters.append(
                    (
                        [embeddings.embeddings[id].id for id in ids],
                        [embeddings.embeddings[id].ref_id for id in ids],
                        [embeddings.embeddings[id].id for id in sample_ids],
                        [embeddings.embeddings[id].ref_id for id in sample_ids],
                    )
                )

            clusters = sorted(clusters, key=lambda x: len(x[0]), reverse=True)

            output_data.clusters = [
                Cluster(
                    embedding_ids=cluster[0],
                    embedding_ref_ids=cluster[1],
                    sample_embedding_ids=cluster[2],
                    sample_embedding_ref_ids=cluster[3],
                )
                for cluster in clusters
            ]

            return {"cluster_data": output_data}
