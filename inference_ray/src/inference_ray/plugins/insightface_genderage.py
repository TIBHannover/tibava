from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from utils import VideoDecoder
from data import (
    ImagesData,
    ScalarData,
    ListData,
    BboxesData,
    FacesData,
    VideoData,
)
import logging
import numpy as np
from data import DataManager, Data

from typing import Callable, Optional, Dict

import sys
import traceback


class InsightfaceGenderAgeCalculator(AnalyserPlugin):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

        self.input_size = [96, 96]  # from model_zoo.py for Attributeclass
        self.input_std = 128.0
        self.input_mean = 127.5

    def get_2d_matrix(self, scale=None, rotation=None, translation=None):
        # creates 2D affine matrix (partially taken from skimage _geometric.py)
        matrix = np.eye(3, dtype=float)  # dimensionality + 1 (2 + 1)
        if scale is None:
            scale = 1
        if rotation is None:
            rotation = 0
        if translation is None:
            translation = (0, 0)

        ax = (0, 1)
        c, s = np.cos(rotation), np.sin(rotation)
        matrix[ax, ax] = c
        matrix[ax, ax[::-1]] = -s, s
        matrix[:2, :2] *= scale
        matrix[:2, 2] = translation

        return matrix

    def transform(self, img, center, output_size, scl):
        import cv2

        scale_ratio = float(output_size) / scl
        t1 = self.get_2d_matrix(scale=scale_ratio)
        cx = center[0] * scale_ratio
        cy = center[1] * scale_ratio
        t2 = self.get_2d_matrix(translation=(-1 * cx, -1 * cy))
        t3 = self.get_2d_matrix(rotation=0)
        t4 = self.get_2d_matrix(translation=(output_size / 2, output_size / 2))
        t = t2 @ t1
        t = t3 @ t
        t = t4 @ t
        M = t[0:2]
        cropped = cv2.warpAffine(img, M, (output_size, output_size), borderValue=0.0)
        return cropped

    def get_feat(self, imgs):
        import cv2

        if not isinstance(imgs, list):
            imgs = [imgs]
        input_size = self.input_size

        blob = cv2.dnn.blobFromImages(
            imgs,
            1.0 / self.input_std,
            input_size,
            (self.input_mean, self.input_mean, self.input_mean),
            swapRB=True,
        )

        return self.server({"data": blob}, ["gender", "age"])

    def get_genderage(self, iterator, num_faces, parameters, data_manager, callbacks):
        try:
            ages = []
            genders = []
            time = []
            ref_ids = []

            # iterate through images to get face_images and bboxes
            for i, face in enumerate(iterator):
                bbox = face.get("bbox")
                x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h
                center = (x + w) / 2, (y + h) / 2
                scale = self.input_size[0] / (max(w, h) * 1.5)
                aimg = self.transform(
                    face.get("frame"), center, self.input_size[0], scale
                )

                # calculate gender and age of face
                gender_age = self.get_feat(aimg)

                time.append(bbox.time)
                ref_ids.append(face.get("face_id"))
                ages.append(gender_age["age"].flatten())  # float: age / 100
                genders.append(
                    np.exp(
                        gender_age["gender"].flatten() / parameters.get("softmax_temp")
                    )
                    / sum(
                        np.exp(
                            gender_age["gender"].flatten()
                            / parameters.get("softmax_temp")
                        )
                    )
                )  # 0 female; 1 male

                self.update_callbacks(callbacks, progress=i / num_faces)

            self.update_callbacks(callbacks, progress=1.0)
            return {
                "ages": ListData(
                    data=[
                        ScalarData(
                            y=np.asarray(ages),
                            time=time,
                            delta_time=1 / parameters.get("fps"),
                            ref_id=ref_ids,
                        )
                    ],
                    index=["age"],
                ),
                "genders": ListData(
                    data=[
                        ScalarData(
                            y=np.asarray(gender),
                            time=time,
                            delta_time=1 / parameters.get("fps"),
                            ref_id=ref_ids,
                        )
                        for gender in zip(*genders)
                    ],
                    index=["female", "male"],
                ),
            }

        except Exception as e:
            logging.error(f"[InsightfaceGenderAgeCalculator] {repr(e)}")
            exc_type, exc_value, exc_traceback = sys.exc_info()

            traceback.print_exception(
                exc_type,
                exc_value,
                exc_traceback,
                limit=2,
                file=sys.stdout,
            )
        return {}


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "insightface_genderage",
    "model_device": "cpu",
    "model_file": "/models/insightface_genderage/genderage.onnx",
}

default_parameters = {"input_size": (640, 640), "softmax_temp": 0.1}

requires = {"video": VideoData, "bboxes": BboxesData}
provides = {"ages": ListData, "genders": ListData}


@AnalyserPluginManager.export("insightface_video_gender_age_calculator")
class InsightfaceVideoGenderAgeCalculator(
    InsightfaceGenderAgeCalculator,
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
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
        with inputs["video"] as video_data, inputs["bboxes"] as bboxes_data:
            bboxes = bboxes_data.bboxes
            parameters["fps"] = 1 / bboxes[0].delta_time
            assert len(bboxes) > 0

            # decode video to extract bboxes for frames with detected faces

            with video_data.open_video() as f_video:
                video_decoder = VideoDecoder(
                    f_video,
                    fps=parameters.get("fps"),
                    extension=f".{video_data.ext}",
                )

                # video_decoder = VideoDecoder(path=inputs["video"].path, fps=parameters.get("fps"))

                bbox_dict = {}
                num_faces = 0
                for bbox in bboxes:
                    if bbox.time not in bbox_dict:
                        bbox_dict[bbox.time] = []
                    num_faces += 1
                    bbox_dict[bbox.time].append(bbox)

                def get_iterator(video_decoder, bbox_dict):
                    # TODO: change VideoDecoder class to be able to directly seek the video for specific frames
                    # WORKAROUND: loop over the whole video and store frames whenever there is a face detected
                    for frame in video_decoder:
                        t = frame["time"]
                        if t in bbox_dict:
                            for bbox in bbox_dict[t]:
                                yield {
                                    "frame": frame["frame"],
                                    "bbox": bbox,
                                    "face_id": bbox.ref_id,
                                }

                iterator = get_iterator(video_decoder, bbox_dict)
                return self.get_genderage(
                    iterator=iterator,
                    num_faces=num_faces,
                    parameters=parameters,
                    data_manager=data_manager,
                    callbacks=callbacks,
                )


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "insightface_genderage",
    "model_device": "cpu",
    "model_file": "/models/insightface_genderage/genderage.onnx",
}

default_parameters = {"input_size": (640, 640), "softmax_temp": 0.1}

requires = {"images": ImagesData, "bboxes": BboxesData}
provides = {"ages": ListData, "genders": ListData}


# @AnalyserPluginManager.export("insightface_image_gender_age_calculator")
# class InsightfaceImageGenderAgeCalculator(
#     InsightfaceVideoGenderAgeCalculator,
#     AnalyserPlugin,
#     config=default_config,
#     parameters=default_parameters,
#     version="0.1",
#     requires=requires,
#     provides=provides,
# ):
#     def __init__(self, config=None, **kwargs):
#         super().__init__(config, **kwargs)

#     def call(
#         self,
#         inputs: Dict[str, Data],
#         data_manager: DataManager,
#         parameters: Dict = None,
#         callbacks: Callable = None,
#     ) -> Dict[str, Data]:
#         with inputs["images"] as images_data, inputs["bboxes"] as bboxes_data:
#             faces = faces_data
#             bboxes = bboxes_data
#             assert len(bboxes) > 0

#             faceid_lut = {}
#             for face in faces:
#                 faceid_lut[face.bbox_id] = face.id

#             image_paths = [
#                 create_data_path(inputs["images"].data_dir, image.id, image.ext) for image in inputs["images"].images
#             ]

#             bbox_dict = {}
#             num_faces = 0
#             for bbox in bboxes:
#                 if bbox.ref_id not in image_paths:
#                     continue

#                 if bbox.ref_id not in bbox_dict:
#                     bbox_dict[bbox.ref_id] = []

#                 num_faces += 1
#                 bbox_dict[bbox.ref_id].append(bbox)

#             def get_iterator(bbox_dict):
#                 for image_path in bbox_dict:
#                     image = iio.imread(image_path)

#                     for bbox in bbox_dict[image_path]:
#                         face_id = faceid_lut[bbox.id] if bbox.id in faceid_lut else None
#                         yield {"frame": image, "bbox": bbox, "face_id": face_id}

#             iterator = get_iterator(bbox_dict)
#             return self.get_genderage(
#                 iterator=iterator,
#                 num_faces=num_faces,
#                 parameters=parameters,
#                 data_manager=data_manager,
#                 callbacks=callbacks,
#             )
