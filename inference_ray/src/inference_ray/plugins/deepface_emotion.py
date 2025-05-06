from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import ListData, ScalarData, ImagesData

# from inference import InferenceServer
from data import DataManager, Data

from typing import Callable, Optional, Dict

import numpy as np
import logging

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "deepface_emotion",
    "model_device": "cpu",
    "model_file": "/models/deepface_emotion/facial_expression_model.onnx",
    "grayscale": True,
    "target_size": (48, 48),
}

default_parameters = {"threshold": 0.5, "reduction": "max"}

requires = {"images": ImagesData}

provides = {
    "probs": ListData,
}


@AnalyserPluginManager.export("deepface_emotion")
class DeepfaceEmotion(
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

        self.grayscale = self.config.get("grayscale")
        self.target_size = self.config.get("target_size")
        self.model_path = self.config.get("model_path")
        self.model = None

    def preprocess(self, img):
        import cv2

        # read image

        # post-processing
        if self.grayscale == True:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # resize image to expected shape
        if img.shape[0] > 0 and img.shape[1] > 0:
            factor_0 = self.target_size[0] / img.shape[0]
            factor_1 = self.target_size[1] / img.shape[1]
            factor = min(factor_0, factor_1)

            dsize = (int(img.shape[1] * factor), int(img.shape[0] * factor))
            img = cv2.resize(img, dsize)

            # Then pad the other side to the target size by adding black pixels
            diff_0 = self.target_size[0] - img.shape[0]
            diff_1 = self.target_size[1] - img.shape[1]
            if self.grayscale == False:
                # Put the base image in the middle of the padded image
                img = np.pad(
                    img,
                    (
                        (diff_0 // 2, diff_0 - diff_0 // 2),
                        (diff_1 // 2, diff_1 - diff_1 // 2),
                        (0, 0),
                    ),
                    "constant",
                )
            else:
                img = np.pad(
                    img,
                    (
                        (diff_0 // 2, diff_0 - diff_0 // 2),
                        (diff_1 // 2, diff_1 - diff_1 // 2),
                    ),
                    "constant",
                )

        if img.shape[0:2] != self.target_size:
            img = cv2.resize(img, self.target_size)

        # normalizing the image pixels
        img_pixels = np.asarray(
            img, np.float32
        )  # TODO same as: keras.preprocessing.image.img_to_array(img)?
        img_pixels = np.expand_dims(img_pixels, axis=0)
        img_pixels /= 255  # normalize input in [0, 1]

        if len(img_pixels.shape) == 3:  # RGB dimension missing
            img_pixels = np.expand_dims(img_pixels, axis=-1)

        return img_pixels

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import onnx
        import onnxruntime

        if self.model is None:

            self.model = onnx.load(self.model_path)
            self.session = onnxruntime.InferenceSession(
                self.model_path,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
        # print(input_name)
        # print(output_name)

        with (
            inputs["images"] as input_data,
            data_manager.create_data("ListData") as output_data,
        ):
            time = []
            ref_ids = []
            predictions = []

            faceid_lut = {}
            faceimages = input_data
            for faceimage in input_data:
                faceid_lut[faceimage.id] = faceimage.ref_id

            for i, entry in enumerate(input_data):
                self.update_callbacks(callbacks, progress=i / len(faceimages))
                image = input_data.load_image(entry)
                image = self.preprocess(image)
                result = self.session.run([self.output_name], {self.input_name: image})
                prediction = result[0][0] if result else None
                face_id = faceid_lut[entry.id] if entry.id in faceid_lut else None

                time.append(entry.time)
                ref_ids.append(face_id)
                predictions.append(prediction.tolist())
                delta_time = entry.delta_time  # same for all examples

            self.update_callbacks(callbacks, progress=1.0)

            index = [
                "p_angry",
                "p_disgust",
                "p_fear",
                "p_happy",
                "p_sad",
                "p_surprise",
                "p_neutral",
            ]
            for i, y in zip(index, zip(*predictions)):
                with output_data.create_data("ScalarData", i) as data:
                    data.y = np.asarray(y)
                    data.time = time
                    data.delta_time = delta_time
                    data.ref_id = ref_ids

            return {"probs": output_data}
