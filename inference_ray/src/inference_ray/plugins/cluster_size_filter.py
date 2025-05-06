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
    "max_cluster": 50,
}

requires = {
    "clusters": ClusterData,
}

provides = {
    "clusters": ClusterData,
}


@AnalyserPluginManager.export("cluster_size_filter")
class ClusterSizeFilter(
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
        with (
            inputs["clusters"] as input_clusters,
            data_manager.create_data("ClusterData") as output_clusters,
        ):
            for cluster in input_clusters.clusters[: parameters.get("max_cluster")]:
                output_clusters.clusters.append(cluster)

            return {"clusters": output_clusters}
