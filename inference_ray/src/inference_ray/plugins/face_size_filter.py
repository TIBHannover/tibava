from typing import Iterator
from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from utils import VideoDecoder
from data import (
    KpssData,
    FacesData,
    ImagesData,
    BboxesData,
    ImageEmbedding,
    ImageEmbeddings,
    VideoData,
)
import logging
import numpy as np
from data import DataManager, Data

from typing import Callable, Optional, Dict


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {"input_size": (640, 640)}

requires = {"video": VideoData, "kpss": KpssData}
provides = {"features": ImageEmbeddings}


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "insightface_w600k_r50",
    "model_device": "cpu",
    "model_file": "/models/insightface_feature_extraction/w600k_r50.onnx",
}

default_parameters = {"min_face_height": 0.1}

requires = {
    "images": Optional[ImagesData],
    "kpss": Optional[KpssData],
    "faces": FacesData,
    "bboxes": BboxesData,
}
provides = {
    "images": Optional[ImagesData],
    "kpss": Optional[KpssData],
    "faces": FacesData,
    "bboxes": BboxesData,
}


@AnalyserPluginManager.export("face_size_filter")
class FaceSizeFilter(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1.3",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        with inputs["faces"] as faces_data, inputs["bboxes"] as bboxes_data:
            selected_ref_ids = []
            for bbox in bboxes_data.bboxes:
                if bbox.h >= parameters.get("min_face_height"):
                    selected_ref_ids.append(bbox.ref_id)

            with data_manager.create_data("BboxesData") as bboxes_output_data:
                for bbox in bboxes_data.bboxes:
                    if bbox.ref_id in selected_ref_ids:
                        bboxes_output_data.bboxes.append(bbox)

            with data_manager.create_data("FacesData") as faces_output_data:
                for face in faces_data.faces:
                    if face.id in selected_ref_ids:
                        faces_output_data.faces.append(face)

        output_dict = {"bboxes": bboxes_output_data, "faces": faces_output_data}

        if "images" in inputs:
            with inputs["images"] as images_data:
                with data_manager.create_data("ImagesData") as images_output_data:
                    for image in images_data.images:
                        if image.ref_id in selected_ref_ids:
                            np_image = images_data.load_image(image)
                            images_output_data.save_image(np_image, **image.to_dict())

                    output_dict["images"] = images_output_data

        if "kpss" in inputs:
            with inputs["kpss"] as kpss_data:
                with data_manager.create_data("KpssData") as kpss_output_data:
                    for kps in kpss_data.kpss:
                        if kps.ref_id in selected_ref_ids:
                            kpss_output_data.kpss.append(kps)

                    output_dict["kpss"] = kpss_output_data
        return output_dict
