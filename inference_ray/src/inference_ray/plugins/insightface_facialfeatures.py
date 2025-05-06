from typing import Iterator
from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from utils import VideoDecoder
from data import (
    KpssData,
    FacesData,
    ImagesData,
    ImageEmbedding,
    ImageEmbeddings,
    VideoData,
)
import logging
import numpy as np
from data import DataManager, Data

from typing import Callable, Optional, Dict


src1 = np.array(
    [
        [51.642, 50.115],
        [57.617, 49.990],
        [35.740, 69.007],
        [51.157, 89.050],
        [57.025, 89.702],
    ],
    dtype=np.float32,
)
# <--left
src2 = np.array(
    [
        [45.031, 50.118],
        [65.568, 50.872],
        [39.677, 68.111],
        [45.177, 86.190],
        [64.246, 86.758],
    ],
    dtype=np.float32,
)

# ---frontal
src3 = np.array(
    [
        [39.730, 51.138],
        [72.270, 51.138],
        [56.000, 68.493],
        [42.463, 87.010],
        [69.537, 87.010],
    ],
    dtype=np.float32,
)

# -->right
src4 = np.array(
    [
        [46.845, 50.872],
        [67.382, 50.118],
        [72.737, 68.111],
        [48.167, 86.758],
        [67.236, 86.190],
    ],
    dtype=np.float32,
)

# -->right profile
src5 = np.array(
    [
        [54.796, 49.990],
        [60.771, 50.115],
        [76.673, 69.007],
        [55.388, 89.702],
        [61.257, 89.050],
    ],
    dtype=np.float32,
)

src = np.array([src1, src2, src3, src4, src5])
src_map = {112: src, 224: src * 2}

arcface_src = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)

arcface_src = np.expand_dims(arcface_src, axis=0)


class InsightfaceFeatureExtractor(AnalyserPlugin):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

        # copied from insightface for w600_r50.onnx model
        self.input_size = tuple([112, 112])
        self.input_std = 127.5
        self.input_mean = 127.5

        self.model = None
        self.model_path = config.get("model_path")

    def estimate_norm(self, lmk, image_size=112, mode="arcface"):
        import cv2

        assert lmk.shape == (5, 2)
        # tform = trans.SimilarityTransform()
        lmk_tran = np.insert(lmk, 2, values=np.ones(5), axis=1)
        min_M = []
        min_index = []
        min_error = float("inf")
        if mode == "arcface":
            if image_size == 112:
                src = arcface_src
            else:
                src = float(image_size) / 112 * arcface_src
        else:
            src = src_map[image_size]
        for i in np.arange(src.shape[0]):
            # tform.estimate(lmk, src[i])
            # M = tform.params[0:2, :]
            M = cv2.estimateAffinePartial2D(lmk, src[i])[0]
            results = np.dot(M, lmk_tran.T)
            results = results.T
            error = np.sum(np.sqrt(np.sum((results - src[i]) ** 2, axis=1)))
            #         print(error)
            if error < min_error:
                min_error = error
                min_M = M
                min_index = i
        return min_M, min_index

    def norm_crop(self, img, landmark, image_size=112, mode="arcface"):
        import cv2

        M, _ = self.estimate_norm(landmark, image_size, mode)
        warped = cv2.warpAffine(img, M, (image_size, image_size), borderValue=0.0)
        return warped

    def get_feat(self, imgs):
        import cv2
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

        result = self.session.run([self.output_name], {self.input_name: blob})[0]
        return result

    def get_facial_features(
        self, iterator, num_faces, parameters, data_manager, callbacks
    ):
        with data_manager.create_data("ImageEmbeddings") as image_embeddings_data:
            # iterate through images to get face_images and bboxes
            for i, face in enumerate(iterator):
                kps = face.get("kps")
                frame = face.get("frame")
                h, w = frame.shape[0:2]
                landmark = np.column_stack([kps.x, kps.y])
                landmark *= (
                    w,
                    h,
                )  # revert normalization done in insightface_detector.py

                aimg = self.norm_crop(face.get("frame"), landmark=landmark)

                image_embeddings_data.embeddings.append(
                    ImageEmbedding(
                        ref_id=face.get("face_id"),
                        embedding=self.get_feat(aimg).flatten(),
                        time=kps.time,
                        delta_time=1 / parameters.get("fps", 1.0),
                    )
                )

                self.update_callbacks(callbacks, progress=i / num_faces)

            self.update_callbacks(callbacks, progress=1.0)
            return {"features": image_embeddings_data}


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "insightface_w600k_r50",
    "model_device": "cpu",
    "model_file": "/models/insightface_feature_extraction/w600k_r50.onnx",
}

default_parameters = {"input_size": (640, 640)}

requires = {"video": VideoData, "kpss": KpssData}
provides = {"features": ImageEmbeddings}


@AnalyserPluginManager.export("insightface_video_feature_extractor")
class InsightfaceVideoFeatureExtractor(
    InsightfaceFeatureExtractor,
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
        with inputs["video"] as video_data, inputs["kpss"] as kpss_data:
            kpss = kpss_data.kpss
            parameters["fps"] = 1 / kpss[0].delta_time
            assert len(kpss) > 0

            faceid_lut = {}
            for kps in kpss:
                faceid_lut[kps.id] = kps.ref_id

            # decode video to extract kps for frames with detected faces

            with video_data.open_video() as f_video:
                video_decoder = VideoDecoder(
                    f_video,
                    fps=parameters.get("fps"),
                    extension=f".{video_data.ext}",
                )
                kps_dict = {}
                num_faces = 0
                for kps in kpss:
                    if kps.time not in kps_dict:
                        kps_dict[kps.time] = []
                    num_faces += 1
                    kps_dict[kps.time].append(kps)

                def get_iterator(video_decoder, kps_dict):
                    # TODO: change VideoDecoder class to be able to directly seek the video for specific frames
                    # WORKAROUND: loop over the whole video and store frames whenever there is a face detected
                    for frame in video_decoder:
                        t = frame["time"]
                        if t in kps_dict:
                            for kps in kps_dict[t]:
                                face_id = (
                                    faceid_lut[kps.id] if kps.id in faceid_lut else None
                                )
                                yield {
                                    "frame": frame["frame"],
                                    "kps": kps,
                                    "face_id": face_id,
                                }

                iterator = get_iterator(video_decoder, kps_dict)
                return self.get_facial_features(
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
    "model_name": "insightface_w600k_r50",
    "model_device": "cpu",
    "model_file": "/models/insightface_feature_extraction/w600k_r50.onnx",
}

default_parameters = {"input_size": (640, 640)}

requires = {"images": ImagesData, "kpss": KpssData, "faces": FacesData}
provides = {"features": ImageEmbeddings}


@AnalyserPluginManager.export("insightface_image_feature_extractor")
class InsightfaceImageFeatureExtractor(
    InsightfaceVideoFeatureExtractor,
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
        with (
            inputs["images"] as images_data,
            inputs["kpss"] as kpss_data,
            inputs["faces"] as faces_data,
        ):
            kpss = kpss_data.kpss
            faces = faces_data.faces
            assert len(kpss) > 0

            image_lut = {image.id: image for image in images_data}
            face_image_lut = {face.id: face.ref_id for face in faces}
            kps_face_lut = {kps.ref_id: kps for kps in kpss}

            def get_iterator():
                for face_id, kps in kps_face_lut.items():
                    if face_id not in face_image_lut:
                        continue
                    image_id = face_image_lut[face_id]
                    if image_id not in image_lut:
                        continue

                    image_data = image_lut[image_id]

                    image = images_data.load_image(image_data)

                    yield {"frame": image, "kps": kps, "face_id": face_id}

            return self.get_facial_features(
                iterator=get_iterator(),
                num_faces=len(kps_face_lut),
                parameters=parameters,
                data_manager=data_manager,
                callbacks=callbacks,
            )
