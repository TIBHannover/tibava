import math
import logging

import numpy as np

import math
import random

from sklearn.preprocessing import MinMaxScaler

from analyser.plugins import MappingPlugin, MappingPluginManager


@MappingPluginManager.export("UMapMapping")
class UMapMapping(MappingPlugin):
    default_config = {
        "random_state": 42,
        "n_neighbors": 3,
        "min_dist": 0.1,
        "grid_method": None,
        "grid_square": True,
    }

    default_version = 0.1

    def __init__(self, **kwargs):
        super(UMapMapping, self).__init__(**kwargs)
        from scipy.spatial import distance_matrix
        from scipy.optimize import linear_sum_assignment

        self.random_state = self.config["random_state"]
        self.n_neighbors = self.config["n_neighbors"]
        self.min_dist = self.config["min_dist"]
        self.grid_method = self.config.get("grid_method", None)
        self.grid_square = self.config.get("grid_square", False)

        if self.grid_method is None:
            self.grid_method = None
        elif self.grid_method.lower() == "scipy":
            self.grid_method = "scipy"
        else:
            logging.warning("[UMapMapping]: Unknown grid_method")
            self.grid_method = None

        logging.info(f"GRID_METHOD {self.grid_method} {kwargs}")

        if self.random_state is None:
            self.random_state = random.randint()

        self.reducer = umap.UMAP(
            random_state=self.random_state,
            n_neighbors=self.n_neighbors,
            min_dist=self.min_dist,
        )

        self.scaler = MinMaxScaler()

    def map_to_scipy_grid(self, entries):

        import umap

        points = np.asarray([x["coordinates"] for x in entries])

        points = (points - np.amin(points)) / (np.amax(points) - np.amin(points))

        num_points = points.shape[0]
        logging.info(f"[UMapMapping::map_to_scipy_grid] num_points: {num_points}")
        if self.grid_square:
            grid_length = math.ceil(math.sqrt(num_points))
            height = grid_length
            width = grid_length
        else:
            height = math.floor(math.sqrt(num_points))
            width = math.ceil(num_points / height)
            grid_length = np.amax([height, width])

        logging.info(
            f"[UMapMapping::map_to_scipy_grid] height:{height} width:{width} grid_length:{grid_length}"
        )
        X, Y = np.mgrid[0:width, 0:height]
        positions = np.transpose(np.vstack([X.ravel(), Y.ravel()])) / grid_length
        # mu_x, std_x = norm.fit(points[:,0])
        # mu_y, std_y = norm.fit(points[:,1])

        d = distance_matrix(points, positions)
        a = linear_sum_assignment(d)
        grid_points = positions[a[1]]
        grid_points = grid_points / np.amax(grid_points, axis=0)

        return [
            {**e, "coordinates": grid_points[i, :].tolist()}
            for i, e in enumerate(entries)
        ]

    def call(self, entries, query):
        ref_feature = "clip_embedding_feature"
        features = []
        entries = list(entries)
        for e in entries:
            for e_f in e["feature"]:
                if ref_feature != e_f["plugin"]:
                    continue
                if "value" in e_f["annotations"][0]:
                    a = e_f["annotations"][0]["value"]
                features.append(a)
        features = np.asarray(features)
        embedding = self.reducer.fit_transform(features)
        normalize_embeddings = self.scaler.fit_transform(embedding)
        new_entries = [
            {**e, "coordinates": normalize_embeddings[i, :].tolist()}
            for i, e in enumerate(entries)
        ]

        if self.grid_method == "scipy":
            new_entries = self.map_to_scipy_grid(new_entries)

        return new_entries
