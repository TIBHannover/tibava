from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from utils import VideoDecoder, image_pad
from data import (
    ListData,
    ImagesData,
    VideoData,
    ListData,
    ImageEmbedding,
    ImageEmbeddings,
    PlaceData,
    PlacesData,
)

import csv
import numpy as np
from data import DataManager, Data

from typing import Callable, Optional, Dict


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "places_classifier",
    "model_device": "cpu",
    "model_file": "/models/places_classification/resnet50_places365.pt",
    "classes_file": "/models/places_classification/categories_places365.txt",
    "hierarchy_file": "/models/places_classification/scene_hierarchy_places365.csv",
    "image_resolution": 224,
}

default_parameters = {"fps": 5}

requires = {
    "video": VideoData,
}

provides = {
    "embedding": ImageEmbeddings,
    "places": PlacesData,
    "probs_places365": ListData,
    "probs_places16": ListData,
    "probs_places3": ListData,
}


@AnalyserPluginManager.export("places_classifier")
class PlacesClassifier(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        # inference_config = self.config.get("inference", None)

        # self.server = InferenceServer.build(inference_config.get("type"), inference_config.get("params", {}))
        self.image_resolution = self.config["image_resolution"]

        self.classes = self.read_classes(
            self.config["classes_file"], self.config["hierarchy_file"]
        )
        self.hierarchy = self.read_hierarchy(self.config["hierarchy_file"])
        self.model_path = self.config.get("model_path")
        self.model = None

    def read_classes(self, classes_file, hierarchy_file):
        classes = {"places365": [], "places16": [], "places3": []}

        with open(classes_file, "r") as csvfile:
            content = csv.reader(csvfile, delimiter=" ")
            for line in content:
                classes["places365"].append(line[0])

        with open(hierarchy_file, "r") as csvfile:
            content = csv.reader(csvfile, delimiter=",")
            next(content)  # skip explanation line
            hierarchy_labels = next(content)  # second row contains hierarchy labels

            classes["places3"] = hierarchy_labels[1:4]
            classes["places16"] = hierarchy_labels[4:]

        return classes

    def read_hierarchy(self, hierarchy_file):
        hierarchy_places3 = []
        hierarchy_places16 = []
        with open(hierarchy_file, "r") as csvfile:
            content = csv.reader(csvfile, delimiter=",")
            next(content)  # skip explanation line
            next(content)  # second row contains hierarchy labels

            for line in content:
                hierarchy_places3.append(line[1:4])
                hierarchy_places16.append(line[4:])

        # normalize label if it belongs to multiple categories
        hierarchy_places3 = np.asarray(hierarchy_places3, dtype=np.float32)
        hierarchy_places3 /= np.expand_dims(np.sum(hierarchy_places3, axis=1), axis=-1)

        hierarchy_places16 = np.asarray(hierarchy_places16, dtype=np.float32)
        hierarchy_places16 /= np.expand_dims(
            np.sum(hierarchy_places16, axis=1), axis=-1
        )

        return {"places3": hierarchy_places3, "places16": hierarchy_places16}

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        from sklearn.preprocessing import normalize
        from sklearn.decomposition import PCA

        import cv2
        import torch
        import math

        device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.model is None:
            self.model = torch.jit.load(
                self.model_path, map_location=torch.device(device)
            )
            self.device = device

        with (
            inputs["video"] as input_data,
            data_manager.create_data("ImageEmbeddings") as embeddings_data,
            data_manager.create_data("ImagesData") as images_data,
            data_manager.create_data("PlacesData") as places_data,
        ):

            with input_data(fps=parameters.get("fps")) as input_iterator:
                probs = {"places365": [], "places16": [], "places3": []}
                time = []
                num_frames = len(input_iterator)
                places_data.places = []

                for i, frame in enumerate(input_iterator):
                    with torch.no_grad(), torch.cuda.amp.autocast():
                        raw_result = self.model(
                            torch.from_numpy(frame["frame"]).to(self.device)
                        )
                    embedding = raw_result[0].cpu().detach().numpy()
                    prob = raw_result[1].cpu().detach().numpy()
                    # result = self.server(
                    #     {"data": np.expand_dims(image_pad(frame["frame"]), axis=0)}, ["embedding", "prob"]
                    # )
                    # store embeddings

                    # store places365 probabilities
                    probs["places365"].append(np.squeeze(np.asarray(prob)))

                    # store places16 probabilities
                    probs["places16"].append(
                        np.matmul(prob, self.hierarchy["places16"])[0]
                    )

                    # store places3 probabilities
                    probs["places3"].append(
                        np.matmul(prob, self.hierarchy["places3"])[0]
                    )

                    # store time
                    time.append(i / parameters.get("fps"))

                    place = PlaceData(
                        ref_id=frame.get("ref_id", None),
                        time=frame.get("time"),
                        place365prob=np.squeeze(np.asarray(prob)),
                        place365class=self.classes["places365"][
                            np.argmax(np.squeeze(np.asarray(prob)))
                        ],
                        place16prob=np.matmul(prob, self.hierarchy["places16"])[0],
                        place16class=self.classes["places16"][
                            np.argmax(np.matmul(prob, self.hierarchy["places16"])[0])
                        ],
                        place3prob=np.matmul(prob, self.hierarchy["places3"])[0],
                        place3class=self.classes["places3"][
                            np.argmax(np.matmul(prob, self.hierarchy["places3"])[0])
                        ],
                    )

                    places_data.places.append(place)

                    images_data.save_image(
                        image=frame.get("frame"),
                        ext="jpg",
                        time=frame.get("time"),
                        delta_time=1 / parameters.get("fps"),
                        ref_id=place.id,
                    )

                    embeddings_data.embeddings.append(
                        ImageEmbedding(
                            embedding=normalize(embedding).flatten(),
                            ref_id=frame.get("id"),
                            time=frame.get("time"),
                            delta_time=1 / parameters.get("fps"),
                        )
                    )

                    self.update_callbacks(callbacks, progress=i / num_frames)

        probs_data = {}
        for level in probs.keys():
            with data_manager.create_data("ListData") as probs_places:
                for index, y in zip(self.classes[level], zip(*probs[level])):
                    with probs_places.create_data("ScalarData", index) as scalar:
                        scalar.y = y
                        scalar.time = time
                        scalar.delta_time = 1 / parameters.get("fps")

                probs_data[level] = probs_places

        self.update_callbacks(callbacks, progress=1.0)
        return {
            "embeddings": embeddings_data,
            "places": places_data,
            "images": images_data,
            "probs_places365": probs_data["places365"],
            "probs_places16": probs_data["places16"],
            "probs_places3": probs_data["places3"],
        }
