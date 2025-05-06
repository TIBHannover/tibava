from pprint import pprint

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from utils import VideoDecoder

from data import (
    BboxData,
    BboxesData,
    StringData,
    StringsData,
    ImagesData,
    VideoData,
    AnnotationData,
    Annotation,
)
from data import DataManager, Data

from typing import Callable, Optional, Dict

from utils import VideoDecoder

import numpy as np
import time
import logging


def merge_lines(
    preds,
    merge_max_x_dist=100,
    merge_min_x_overlap=0.5,
    merge_max_y_dist=10,
    merge_min_y_overlap=0.5,
):
    # merge into lines
    stitched = stitch_boxes_into_lines(
        preds,
        max_dist=merge_max_x_dist,
        min_overlap_ratio=merge_min_y_overlap,
    )

    # flip x,y and stitch based on y (merge longer lines/paragraphs)
    for s in stitched:
        x_max = max(s["box"][::2])
        x_min = min(s["box"][::2])
        y_max = max(s["box"][1::2])
        y_min = min(s["box"][1::2])
        s["box"] = [y_min, x_min, y_max, x_min, y_max, x_max, y_min, x_max]
    stitched = stitch_boxes_into_lines(
        stitched,
        max_dist=merge_max_y_dist,
        min_overlap_ratio=merge_min_x_overlap,
    )

    # flip back
    for s in stitched:
        x_max = max(s["box"][1::2])
        x_min = min(s["box"][1::2])
        y_max = max(s["box"][::2])
        y_min = min(s["box"][::2])
        s["box"] = [x_min, y_min, x_max, y_min, x_max, y_max, x_min, y_max]

    return stitched


def is_on_same_line(box_a, box_b, min_y_overlap_ratio=0.8):
    """https://github.com/open-mmlab/mmocr/blob/2caab0a4e7dff2929ee6113927098384af6072bf/mmocr/utils/bbox_utils.py#L92

    Check if two boxes are on the same line by their y-axis coordinates.

    Two boxes are on the same line if they overlap vertically, and the length
    of the overlapping line segment is greater than min_y_overlap_ratio * the
    height of either of the boxes.

    Args:
        box_a (list), box_b (list): Two bounding boxes to be checked
        min_y_overlap_ratio (float): The minimum vertical overlapping ratio
                                    allowed for boxes in the same line

    Returns:
        The bool flag indicating if they are on the same line
    """
    a_y_min = np.min(box_a[1::2])
    b_y_min = np.min(box_b[1::2])
    a_y_max = np.max(box_a[1::2])
    b_y_max = np.max(box_b[1::2])

    # Make sure that box a is always the box above another
    if a_y_min > b_y_min:
        a_y_min, b_y_min = b_y_min, a_y_min
        a_y_max, b_y_max = b_y_max, a_y_max

    if b_y_min <= a_y_max:
        if min_y_overlap_ratio is not None:
            sorted_y = sorted([b_y_min, b_y_max, a_y_max])
            overlap = sorted_y[1] - sorted_y[0]
            min_a_overlap = (a_y_max - a_y_min) * min_y_overlap_ratio
            min_b_overlap = (b_y_max - b_y_min) * min_y_overlap_ratio
            return overlap >= min_a_overlap or overlap >= min_b_overlap
        else:
            return True
    return False


def stitch_boxes_into_lines(
    boxes,
    max_dist=10,
    min_overlap_ratio=0.8,
):
    """Stitch fragmented boxes of words into lines.

    Note: part of its logic is inspired by @Johndirr
    (https://github.com/faustomorales/keras-ocr/issues/22)

    Args:
        boxes (list): List of ocr results to be stitched
        max_x_dist (int): The maximum horizontal distance between the closest
                    edges of neighboring boxes in the same line
        min_y_overlap_ratio (float): The minimum vertical overlapping ratio
                    allowed for any pairs of neighboring boxes in the same line

    Returns:
        merged_boxes(list[dict]): List of merged boxes and texts
    """
    if len(boxes) <= 1:
        return boxes

    merged_boxes = []

    # sort groups based on the x_min coordinate of boxes
    x_sorted_boxes = sorted(boxes, key=lambda x: np.min(x["box"][::2]))
    # store indexes of boxes which are already parts of other lines
    skip_idxs = set()

    i = 0
    # locate lines of boxes starting from the leftmost one
    for i in range(len(x_sorted_boxes)):
        if i in skip_idxs:
            continue
        # the rightmost box in the current line
        rightmost_box_idx = i
        line = [rightmost_box_idx]
        for j in range(i + 1, len(x_sorted_boxes)):
            if j in skip_idxs:
                continue
            if is_on_same_line(
                x_sorted_boxes[rightmost_box_idx]["box"],
                x_sorted_boxes[j]["box"],
                min_overlap_ratio,
            ):
                line.append(j)
                skip_idxs.add(j)
                rightmost_box_idx = j

        # split line into lines if the distance between two neighboring
        # sub-lines' is greater than max_x_dist
        lines = []
        line_idx = 0
        lines.append([line[0]])
        for k in range(1, len(line)):
            curr_box = x_sorted_boxes[line[k]]
            prev_box = x_sorted_boxes[line[k - 1]]
            dist = np.min(curr_box["box"][::2]) - np.max(prev_box["box"][::2])
            # current_line = ' '.join([x_sorted_boxes[i]['text'] for i in lines[line_idx]])
            # current_word = x_sorted_boxes[line[k]]['text']
            if dist > max_dist:
                line_idx += 1
                lines.append([])
            lines[line_idx].append(line[k])

        # Get merged boxes
        for box_group in lines:
            merged_box = {}
            merged_box["text"] = " ".join(
                [x_sorted_boxes[idx]["text"] for idx in box_group]
            )
            x_min, y_min = float("inf"), float("inf")
            x_max, y_max = float("-inf"), float("-inf")
            for idx in box_group:
                x_max = max(np.max(x_sorted_boxes[idx]["box"][::2]), x_max)
                x_min = min(np.min(x_sorted_boxes[idx]["box"][::2]), x_min)
                y_max = max(np.max(x_sorted_boxes[idx]["box"][1::2]), y_max)
                y_min = min(np.min(x_sorted_boxes[idx]["box"][1::2]), y_min)
            merged_box["box"] = [x_min, y_min, x_max, y_min, x_max, y_max, x_min, y_max]
            merged_boxes.append(merged_box)
        # print(f'Merges process {multiprocessing.current_process().ident} released lock on Bert process num {bert_processs_id}')

    return merged_boxes


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


def letterbox(
    im, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleup=True, stride=32
):
    import cv2

    # Resize and pad image while meeting stride-multiple constraints
    shape = im.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:  # only scale down, do not scale up (for better val mAP)
        r = min(r, 1.0)

    # Compute padding
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh padding

    if auto:  # minimum rectangle
        dw, dh = np.mod(dw, stride), np.mod(dh, stride)  # wh padding

    dw /= 2  # divide padding into 2 sides
    dh /= 2

    if shape[::-1] != new_unpad:  # resize
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(
        im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color
    )  # add border
    return im, r, (dw, dh)


def image_preprocess(image, target_size):
    import cv2

    ih, iw = target_size
    h, w, _ = image.shape

    scale = min(iw / w, ih / h)
    nw, nh = int(scale * w), int(scale * h)
    image_resized = cv2.resize(image, (nw, nh))

    image_padded = np.full(shape=[ih, iw, 3], fill_value=128.0)
    dw, dh = (iw - nw) // 2, (ih - nh) // 2
    image_padded[dh : nh + dh, dw : nw + dw, :] = image_resized
    image_padded = image_padded / 255.0

    return image_padded


class OCRTextDetectorONNX(AnalyserPlugin):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

        self.textdet_model_path = self.config.get("model_path")
        self.textdet_model = None
        self.textrec_model = None

    def forward_nms(self, data, det_thresh, nms_thresh, dwdh, ratio):
        import torch

        start_time = time.time()
        scores_list = []
        bboxes_list = []
        with torch.no_grad(), torch.cuda.amp.autocast():
            raw_result = self.session.run(
                [self.output_name], {self.input_name: data.astype(np.float32)}
            )

        start_time = time.time()

        for i, (batch_id, x0, y0, x1, y1, cls_id, score) in enumerate(raw_result[0]):
            box = np.array([x0, y0, x1, y1])
            box -= np.array(dwdh * 2)
            box /= ratio
            box = box.round().astype(np.int32).tolist()
            score = round(float(score), 3)
            bboxes_list.append(box)
            scores_list.append(score)

        bboxes = np.vstack(bboxes_list)
        scores = np.vstack(scores_list)
        scores_ravel = scores.ravel()
        order = scores_ravel.argsort()[::-1]
        pre_det = np.hstack((bboxes, scores)).astype(np.float32, copy=False)
        pre_det = pre_det[order, :]
        keep = nms(pre_det, nms_thresh)
        det = pre_det[keep, :]

        # print(f"API {time.time() - start_time}")
        return {"boxes": det[:, :4], "scores": det[:, 4]}

    def detect(
        self,
        frame,
        input_size=(640, 640),
        det_thresh=0.5,
        nms_thresh=0.4,
        fps=10,
    ):
        import onnx
        import torch
        import onnxruntime
        import cv2

        if self.textdet_model is None:

            self.textdet_model = onnx.load(self.textdet_model_path)
            self.session = onnxruntime.InferenceSession(
                self.textdet_model_path, providers=["CUDAExecutionProvider"]
            )
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name

            torch.hub.set_dir("/models/ocr")
            self.textrec_model = torch.hub.load(
                "baudm/parseq", "parseq", pretrained=True, device="cuda"
            ).eval()

        original_image = frame.get("frame")

        input_size = 640
        original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        image, ratio, dwdh = letterbox(original_image, auto=False)
        image_data = image_preprocess(np.copy(original_image), [input_size, input_size])
        image_data = np.moveaxis(image_data, -1, 0)
        image_data = image_data[np.newaxis, ...].astype(np.float32)

        result = self.forward_nms(
            data=image_data,
            det_thresh=det_thresh,
            nms_thresh=nms_thresh,
            dwdh=dwdh,
            ratio=ratio,
        )

        bboxes = result["boxes"]
        scores = result["scores"]

        # create bbox, and string objects (added to original code)
        bbox_list = []
        for i in range(len(scores)):
            x, y = round(max(0, bboxes[i][0])), round(max(0, bboxes[i][1]))
            w, h = round(bboxes[i][2] - x), round(bboxes[i][3] - y)
            det_score = scores[i]

            if w == 0.0 or h == 0.0:
                continue

            bbox = {
                "x": float(x),
                "y": float(y),
                "w": float(w),
                "h": float(h),
                "det_score": float(det_score),
                "time": frame.get("time"),
                "delta_time": 1 / fps,
            }
            bbox_list.append(bbox)

        return bbox_list

    def predict_texts(self, iterator, num_frames, parameters, data_manager, callbacks):
        import torch

        with (
            data_manager.create_data("ImagesData") as images_data,
            data_manager.create_data("BboxesData") as bboxes_data,
            data_manager.create_data("StringsData") as strings_data,
            data_manager.create_data("AnnotationData") as annotations_data,
        ):

            # iterate through images to get strings and bboxes
            for fidx, frame in enumerate(iterator):
                self.update_callbacks(callbacks, progress=fidx / num_frames)
                frame_bboxes = self.detect(
                    frame,
                    parameters.get("input_size"),
                    det_thresh=parameters.get("det_thresh"),
                    nms_thresh=parameters.get("nms_thresh"),
                    fps=parameters.get("fps"),
                )

                cropped_images = []

                for i in range(len(frame_bboxes)):
                    # store bboxes, and strings
                    text = StringData(ref_id=frame.get("ref_id", None))
                    text.text = "test"
                    bbox = BboxData(**frame_bboxes[i], ref_id=text.id)

                    # bboxes_data.bboxes.append(bbox)
                    # strings_data.strings.append(text)

                    # store string image
                    frame_image = frame.get("frame")
                    h, w = frame_image.shape[:2]

                    # write string image
                    text_image = frame_image[
                        round(bbox.y) : round(bbox.y + bbox.h),
                        round(bbox.x) : round((bbox.x + bbox.w)),
                        :,
                    ]

                    # resize image to self.textrec_model.hparams.img_size size
                    processed_cropped_image = image_preprocess(
                        text_image, self.textrec_model.hparams.img_size
                    )

                    # convert to tensor
                    processed_cropped_image = torch.tensor(
                        processed_cropped_image
                    ).permute(2, 0, 1)

                    # normalize image with mean and std of 0.5
                    processed_cropped_image = (processed_cropped_image - 0.5) / 0.5

                    cropped_images.append(processed_cropped_image)

                    images_data.save_image(
                        text_image,
                        ext="jpg",
                        time=frame.get("time"),
                        delta_time=1 / parameters.get("fps"),
                        ref_id=text.id,
                    )

                if not cropped_images:
                    continue

                # predict strings
                cropped_images: torch.Tensor = torch.stack(cropped_images).type(
                    torch.float32
                )
                strings: list[str] = []
                with torch.no_grad():
                    logits = self.textrec_model(cropped_images)
                    logits.shape  # torch.Size([1, 26, 95]), 94 characters + [EOS] symbol

                    # Greedy decoding
                    pred = logits.softmax(-1)
                    labels, confidence = self.textrec_model.tokenizer.decode(pred)
                    strings = labels

                    # for i in range(len(frame_bboxes)):
                    #     strings_data.strings[fidx + i].text = labels[i]

                    # end_time = frame.get("time") + 1 / parameters.get("fps")

                    # annotations_data.annotations.append(
                    #     Annotation(
                    #         start=frame.get("time"), end=end_time, labels=labels
                    #     )
                    # )

                # merge words into lines
                bbox_list: list[dict] = []
                for i in range(len(frame_bboxes)):
                    box = {}
                    box["box"] = np.array(
                        [
                            frame_bboxes[i]["x"],
                            frame_bboxes[i]["y"],
                            frame_bboxes[i]["x"] + frame_bboxes[i]["w"],
                            frame_bboxes[i]["y"],
                            frame_bboxes[i]["x"] + frame_bboxes[i]["w"],
                            frame_bboxes[i]["y"] + frame_bboxes[i]["h"],
                            frame_bboxes[i]["x"],
                            frame_bboxes[i]["y"] + frame_bboxes[i]["h"],
                        ]
                    )
                    box["text"] = strings[i]
                    bbox_list.append(box)

                stitched = merge_lines(bbox_list)

                # add the merged boxes to bbox_data and strings_data
                for i in range(len(stitched)):
                    box = stitched[i]
                    bbox = BboxData(
                        x=box["box"][0],
                        y=box["box"][1],
                        w=box["box"][2] - box["box"][0],
                        h=box["box"][5] - box["box"][1],
                        det_score=0.0,
                        time=frame.get("time"),
                        delta_time=1 / parameters.get("fps"),
                    )
                    # bboxes_data.bboxes.append(bbox)

                    text = StringData(ref_id=bbox.id)
                    text.text = box["text"]
                    strings_data.strings.append(text)

                    end_time = frame.get("time") + 1 / parameters.get("fps")
                    annotations_data.annotations.append(
                        Annotation(
                            start=frame.get("time"), end=end_time, labels=[box["text"]]
                        )
                    )

                # if fidx % 10 == 0:
                #     print(f"Processed {fidx} frames")

            self.update_callbacks(callbacks, progress=1.0)

            return {
                "images": images_data,
                "bboxes": bboxes_data,
                "strings": strings_data,
                "annotations": annotations_data,
            }


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "ocr_onnx",
    "model_device": "gpu",
    "model_file": "/models/ocr/yolov7_text_det_dyn_input.onnx",
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
    "strings": StringsData,
    "annotations": AnnotationData,
}


@AnalyserPluginManager.export("ocr_video_detector_onnx")
class OCRVideoDetectorONNX(
    OCRTextDetectorONNX,
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

                num_frames = video_decoder.duration() * video_decoder.fps()

                return self.predict_texts(
                    iterator=video_decoder,
                    num_frames=num_frames,
                    parameters=parameters,
                    data_manager=data_manager,
                    callbacks=callbacks,
                )
