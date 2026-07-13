import os
import re
import h5py

import numpy as np

import logging

import uuid
import pickle

from multiprocessing import Lock


class Cache:
    def __init__(self, cache_dir, mode="a"):
        self.cache_dir = cache_dir

        os.makedirs(self.cache_dir, exist_ok=True)

        self.cache_data = {"classifier": {}, "feature": {}}
        self.classifier_data = {}
        self.feature_data = {}

        self.length = 4096

        self.num_client = 0
        self.mutex = Lock()
        self.dirty = False
        self.mode = mode

    def __enter__(self):

        with self.mutex:
            if self.num_client == 0:
                logging.info("Cache: Read cache files")
                if os.path.exists(os.path.join(self.cache_dir, "data.pkl")):
                    with open(os.path.join(self.cache_dir, "data.pkl"), "rb") as f:
                        self.cache_data = pickle.load(f)

                    logging.info("Cache: 1")
                    for _, c in self.cache_data["classifier"].items():
                        logging.info(os.path.join(self.cache_dir, f"{c['id']}.pkl"))
                        with open(os.path.join(self.cache_dir, f"{c['id']}.pkl"), "rb") as f:
                            self.classifier_data[c["cache_name"]] = pickle.load(f)

                    logging.info("Cache: 2")
                    for _, c in self.cache_data["feature"].items():
                        logging.info(os.path.join(self.cache_dir, f"{c['id']}.h5"))
                        index_id = c["id"]
                        self.feature_data[c["cache_name"]] = {
                            "h5": h5py.File(os.path.join(self.cache_dir, f"{index_id}.h5"), self.mode),
                            "max_size": 0,
                        }
                        self.feature_data[c["cache_name"]]["max_size"] = self.feature_data[c["cache_name"]]["h5"][
                            "data"
                        ].shape[0]
                        print(self.feature_data[c["cache_name"]])
                    logging.info("Cache: 3")

            self.num_client += 1

        return self

    def __exit__(self, type, value, tb):

        if self.mode == "r":
            return

        with self.mutex:
            if self.num_client == 1 and self.dirty:
                logging.info("Cache: Save cache files")
                with open(os.path.join(self.cache_dir, "data.pkl"), "wb") as f:
                    pickle.dump(self.cache_data, f)

                for _, c in self.cache_data["classifier"].items():

                    with open(os.path.join(self.cache_dir, f"{c['id']}.pkl"), "wb") as f:
                        pickle.dump(self.classifier_data[c["cache_name"]], f)

                for _, c in self.cache_data["feature"].items():

                    self.feature_data[c["cache_name"]]["h5"].close()
            self.num_client -= 1

    def __getitem__(self, id):
        data_dict = {"id": id, "classifier": [], "feature": []}

        for cache_name, cache in self.cache_data["classifier"].items():
            if id in self.classifier_data[cache_name]:
                data_dict["classifier"].append(self.classifier_data[cache_name][id])

        for cache_name, cache in self.cache_data["feature"].items():
            if id in cache["entries"]:
                h5_index = cache["entries"][id]
                feature = self.feature_data[cache_name]["h5"]["data"][h5_index].tolist()
                data_dict["feature"].append(
                    {"plugin": cache["plugin"], "type": cache["type"], "version": cache["version"], "value": feature}
                )

        return data_dict

    def write(self, entry):
        if self.mode == "r":
            return

        with self.mutex:
            self.dirty = True
            id = entry["id"]
            if "classifier" in entry:
                for c in entry["classifier"]:
                    cache_name = f"{c['plugin']}.{c['version']}"
                    if cache_name not in self.cache_data["classifier"]:
                        self.cache_data["classifier"][cache_name] = {
                            "id": uuid.uuid4().hex,
                            "cache_name": cache_name,
                            "plugin": c["plugin"],
                            "version": c["version"],
                        }

                    if cache_name not in self.classifier_data:
                        self.classifier_data[cache_name] = {}
                    self.classifier_data[cache_name][id] = c

            if "feature" in entry:
                for c in entry["feature"]:
                    cache_name = f"{c['plugin']}.{c['type']}.{c['version']}"
                    if cache_name not in self.cache_data["feature"]:
                        self.cache_data["feature"][cache_name] = {
                            "id": uuid.uuid4().hex,
                            "cache_name": cache_name,
                            "entries": {},
                            "d": len(c["value"]),
                            "type": c["type"],
                            "plugin": c["plugin"],
                            "version": c["version"],
                        }

                    if cache_name not in self.feature_data:
                        index_id = self.cache_data["feature"][cache_name]["id"]
                        self.feature_data[cache_name] = {
                            "h5": h5py.File(os.path.join(self.cache_dir, f"{index_id}.h5"), "a"),
                            "max_size": self.length,
                        }

                        self.feature_data[cache_name]["h5"].create_dataset(
                            "data", [self.length] + [len(c["value"])], dtype=float, maxshape=[None] + [len(c["value"])]
                        )

                    self.feature_data[cache_name]["h5"]["data"][
                        len(self.cache_data["feature"][cache_name]["entries"])
                    ] = c["value"]

                    if id not in self.cache_data["feature"][cache_name]["entries"]:
                        self.cache_data["feature"][cache_name]["entries"][id] = len(
                            self.cache_data["feature"][cache_name]["entries"]
                        )

                    if (
                        len(self.cache_data["feature"][cache_name]["entries"])
                        >= self.feature_data[cache_name]["max_size"]
                    ):
                        self.feature_data[cache_name]["max_size"] += self.length
                        self.feature_data[cache_name]["h5"]["data"].resize(
                            self.feature_data[cache_name]["max_size"], axis=0
                        )
