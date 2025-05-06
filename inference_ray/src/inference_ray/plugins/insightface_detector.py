from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from utils import VideoDecoder

from data import (
    BboxData,
    BboxesData,
    FaceData,
    FacesData,
    KpsData,
    KpssData,
    ImageData,
    ImagesData,
    VideoData,
)
from data import DataManager, Data

from typing import Callable, Optional, Dict
import numpy as np
import time


def distance2bbox(points, distance, max_shape=None):
    """Decode distance prediction to bounding box.
    Args:
        points (Tensor): Shape (n, 2), [x, y].
        distance (Tensor): Distance from the given point to 4
            boundaries (left, top, right, bottom).
        max_shape (tuple): Shape of the image.
    Returns:
        Tensor: Decoded bboxes.
    """
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    if max_shape is not None:
        x1 = x1.clamp(min=0, max=max_shape[1])
        y1 = y1.clamp(min=0, max=max_shape[0])
        x2 = x2.clamp(min=0, max=max_shape[1])
        y2 = y2.clamp(min=0, max=max_shape[0])
    return np.stack([x1, y1, x2, y2], axis=-1)


def distance2kps(points, distance, max_shape=None):
    """Decode distance prediction to bounding box.
    Args:
        points (Tensor): Shape (n, 2), [x, y].
        distance (Tensor): Distance from the given point to 4
            boundaries (left, top, right, bottom).
        max_shape (tuple): Shape of the image.
    Returns:
        Tensor: Decoded bboxes.
    """
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, i % 2] + distance[:, i]
        py = points[:, i % 2 + 1] + distance[:, i + 1]
        if max_shape is not None:
            px = px.clamp(min=0, max=max_shape[1])
            py = py.clamp(min=0, max=max_shape[0])
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)


def nms(dets, nms_thresh):
    thresh = nms_thresh
    x1 = dets[:, 0]
    y1 = dets[:, 1]
    x2 = dets[:, 2]
    y2 = dets[:, 3]
    scores = dets[:, 4]

    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)

        inds = np.where(ovr <= thresh)[0]
        order = order[inds + 1]

    return keep


class InsightfaceDetectorTorch(AnalyserPlugin):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        # inference_config = self.config.get("inference", None)

        # self.server = InferenceServer.build(inference_config.get("type"), inference_config.get("params", {}))
        self.model_path = self.config.get("model_path")
        self.model = None

    def forward_nms(self, data, det_thresh, nms_thresh):
        import torch

        # data = dict_to_numpy(input.get("data"))
        # det_thresh = input.get("det_thresh")
        # nms_thresh = input.get("nms_thresh")
        start_time = time.time()
        # data = np.asarray(input.data)
        feat_stride_fpn = [8, 16, 32]
        fmc = 3
        num_anchors = 2
        input_height = data.shape[1]
        input_width = data.shape[2]
        center_cache = {}
        scores_list = []
        bboxes_list = []
        kpss_list = []
        with torch.no_grad(), torch.cuda.amp.autocast():
            raw_result = self.model(torch.from_numpy(data).to(self.device))

        print(f"RUNNER {time.time() - start_time}")
        start_time = time.time()
        # result = self.con.modelrun(self.model_name, f"data_{job_id}", output_names)
        # net_outs = self.session.run(self.output_names, {self.input_name : blob})  # original function
        net_outs = [x[0, :, :].cpu().detach().numpy() for x in raw_result]
        # print(net_outs[0][:5, :5])
        # for x in net_outs:
        #     print(x.shape)
        # exit()

        for idx, stride in enumerate(feat_stride_fpn):
            scores = net_outs[idx]
            bbox_preds = net_outs[idx + fmc]
            bbox_preds = bbox_preds * stride
            kps_preds = net_outs[idx + fmc * 2] * stride

            height = input_height // stride
            width = input_width // stride
            K = height * width
            key = (height, width, stride)
            if key in center_cache:
                anchor_centers = center_cache[key]
            else:
                anchor_centers = np.stack(
                    np.mgrid[:height, :width][::-1], axis=-1
                ).astype(np.float32)
                anchor_centers = (anchor_centers * stride).reshape((-1, 2))
                if num_anchors > 1:
                    anchor_centers = np.stack(
                        [anchor_centers] * num_anchors, axis=1
                    ).reshape((-1, 2))
                if len(center_cache) < 100:
                    center_cache[key] = anchor_centers

            pos_inds = np.where(scores >= det_thresh)[0]
            bboxes = distance2bbox(anchor_centers, bbox_preds)
            pos_scores = scores[pos_inds]
            pos_bboxes = bboxes[pos_inds]
            scores_list.append(pos_scores)
            bboxes_list.append(pos_bboxes)
            kpss = distance2kps(anchor_centers, kps_preds)
            # kpss = kps_preds
            kpss = kpss.reshape((kpss.shape[0], -1, 2))
            pos_kpss = kpss[pos_inds]
            kpss_list.append(pos_kpss)
        bboxes = np.vstack(bboxes_list)
        kpss = np.vstack(kpss_list)
        scores = np.vstack(scores_list)
        scores_ravel = scores.ravel()
        order = scores_ravel.argsort()[::-1]
        pre_det = np.hstack((bboxes, scores)).astype(np.float32, copy=False)
        pre_det = pre_det[order, :]
        keep = nms(pre_det, nms_thresh)
        det = pre_det[keep, :]

        kpss = kpss[order, :, :]
        kpss = kpss[keep, :, :]

        print(f"API {time.time() - start_time}")
        return {
            "boxes": det[:, :4],
            "scores": det[:, 4],
            "kpss": kpss,
        }

    def detect(
        self,
        frame,
        input_size=(640, 640),
        det_thresh=0.5,
        nms_thresh=0.4,
        fps=10,
    ):
        import cv2
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.model is None:
            self.model = torch.jit.load(
                self.model_path, map_location=torch.device(device)
            )
            self.device = device

        img = frame.get("frame")
        im_ratio = float(img.shape[0]) / img.shape[1]
        model_ratio = float(input_size[1]) / input_size[0]
        if im_ratio > model_ratio:
            new_height = input_size[1]
            new_width = int(new_height / im_ratio)
        else:
            new_width = input_size[0]
            new_height = int(new_width * im_ratio)
        det_scale = float(new_height) / img.shape[0]
        resized_img = cv2.resize(img, (new_width, new_height))
        det_img = np.zeros((input_size[1], input_size[0], 3), dtype=np.uint8)
        det_img[:new_height, :new_width, :] = resized_img
        start_time = time.time()
        result = self.forward_nms(
            data=np.expand_dims(det_img, axis=0),
            det_thresh=det_thresh,
            nms_thresh=nms_thresh,
        )

        bboxes = result["boxes"] / det_scale
        kpss = result["kpss"] / det_scale
        scores = result["scores"]

        # create bbox, kps, and face objects (added to original code)
        bbox_list = []
        kps_list = []
        for i in range(len(scores)):
            x, y = round(max(0, bboxes[i][0])), round(max(0, bboxes[i][1]))
            w, h = round(bboxes[i][2] - x), round(bboxes[i][3] - y)
            det_score = scores[i]

            # store bbox
            bbox = {
                "x": float(x / img.shape[1]),
                "y": float(y / img.shape[0]),
                "w": float(w / img.shape[1]),
                "h": float(h / img.shape[0]),
                "det_score": float(det_score),
                "time": frame.get("time"),
                "delta_time": 1 / fps,
            }
            bbox_list.append(bbox)

            # store facial keypoints (kps)
            kps = {
                "x": [x.item() / img.shape[1] for x in kpss[i, :, 0]],
                "y": [y.item() / img.shape[0] for y in kpss[i, :, 1]],
                "time": frame.get("time"),
                "delta_time": 1 / fps,
            }
            kps_list.append(kps)

        return bbox_list, kps_list

    def predict_faces(self, iterator, num_frames, parameters, data_manager, callbacks):
        with (
            data_manager.create_data("ImagesData") as images_data,
            data_manager.create_data("BboxesData") as bboxes_data,
            data_manager.create_data("FacesData") as faces_data,
            data_manager.create_data("KpssData") as kpss_data,
        ):
            # iterate through images to get face_images and bboxes
            for i, frame in enumerate(iterator):
                self.update_callbacks(callbacks, progress=i / num_frames)
                frame_bboxes, frame_kpss = self.detect(
                    frame,
                    parameters.get("input_size"),
                    det_thresh=parameters.get("det_thresh"),
                    nms_thresh=parameters.get("nms_thresh"),
                    fps=parameters.get("fps"),
                )

                for i in range(len(frame_bboxes)):
                    # store bboxes, kpss, and faces
                    face = FaceData(ref_id=frame.get("ref_id", None))
                    bbox = BboxData(**frame_bboxes[i], ref_id=face.id)
                    kps = KpsData(**frame_kpss[i], ref_id=face.id)

                    # faces.append(face)
                    # bboxes.append(bbox)
                    # kpss.append(kps)
                    bboxes_data.bboxes.append(bbox)
                    faces_data.faces.append(face)
                    kpss_data.kpss.append(kps)

                    # store face image
                    frame_image = frame.get("frame")
                    h, w = frame_image.shape[:2]

                    # draw kps
                    # for i in range(len(kps.x)):
                    #     x = round(kps.x[i] * w)
                    #     y = round(kps.y[i] * h)
                    #     frame_image[y - 1 : y + 1, x - 1 : x + 1, :] = [0, 255, 0]

                    # write faceimg
                    face_image = frame_image[
                        round(bbox.y * h) : round((bbox.y + bbox.h) * h),
                        round(bbox.x * w) : round((bbox.x + bbox.w) * w),
                        :,
                    ]

                    images_data.save_image(
                        face_image,
                        ext="jpg",
                        time=frame.get("time"),
                        delta_time=1 / parameters.get("fps"),
                        ref_id=face.id,
                    )
            self.update_callbacks(callbacks, progress=1.0)

            return {
                "images": images_data,
                "bboxes": bboxes_data,
                "kpss": kpss_data,
                "faces": faces_data,
            }


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "insightface_torch",
    "model_device": "cpu",
    "model_file": "/models/insightface_detector_torch/scrfd_10g_bnkps.pth",
}

default_parameters = {
    "fps": 2,
    "det_thresh": 0.5,
    "nms_thresh": 0.4,
    "input_size": (640, 640),
}

requires = {
    "video": VideoData,
}

provides = {
    "images": ImagesData,
    "bboxes": BboxesData,
    "kpss": KpssData,
    "faces": FacesData,
}


@AnalyserPluginManager.export("insightface_video_detector_torch")
class InsightfaceVideoDetectorTorch(
    InsightfaceDetectorTorch,
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
        with inputs["video"] as input_data:
            with input_data.open_video() as f_video:
                video_decoder = VideoDecoder(
                    f_video,
                    fps=parameters.get("fps"),
                    extension=f".{input_data.ext}",
                    ref_id=input_data.id,
                )

                # decode video to extract bboxes per frame
                # video_decoder = VideoDecoder(path=inputs["video"].path, fps=parameters.get("fps"))

                num_frames = video_decoder.duration() * video_decoder.fps()

                return self.predict_faces(
                    iterator=video_decoder,
                    num_frames=num_frames,
                    parameters=parameters,
                    data_manager=data_manager,
                    callbacks=callbacks,
                )


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "insightface_torch",
    "model_device": "cpu",
    "model_file": "/models/insightface_detector_torch/scrfd_10g_bnkps.pth",
}

default_parameters = {
    "fps": 1,
    "det_thresh": 0.5,
    "nms_thresh": 0.4,
    "input_size": (640, 640),
}

requires = {
    "images": ImagesData,
}

provides = {
    "images": ImagesData,
    "bboxes": BboxesData,
    "kpss": KpssData,
    "faces": FacesData,
}


@AnalyserPluginManager.export("insightface_image_detector_torch")
class InsightfaceImageDetectorTorch(
    InsightfaceDetectorTorch,
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
        with inputs["images"] as input_data:

            def image_generator():
                for image in input_data:
                    frame = input_data.load_image(image)

                    yield {"frame": frame, "time": 0, "ref_id": image.id}

            images = image_generator()
            return self.predict_faces(
                iterator=images,
                num_frames=len(input_data),
                parameters=parameters,
                data_manager=data_manager,
                callbacks=callbacks,
            )
