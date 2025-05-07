from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import BboxesData, AnnotationData, Annotation, ShotsData, FacesData

from data import DataManager, Data

import logging

import numpy as np
from typing import Callable, Any, Dict, List
from collections import defaultdict

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {
    "fps": 25,  # detected automatically by bbox delta_time
    "min_track": 1,  # in seconds instead of frames (25)
    "num_failed_det": 10,
    "min_face_size": 0,  # TODO adapt min_face_size check to normalized bboxes, hard constrained already included: bbox.h > 0.05
    "crop_scale": 0.4,
    "workers": 4,
}

requires = {
    "bboxes": BboxesData,
    "faces": FacesData,  # TODO does not contain any information? remove
    "shots": ShotsData,
}

provides = {
    "track_data": AnnotationData,
}
""" Annotation label objects:
{
"frames": frame indices
"bboxes": normalized x1y1x2y2 format #TODO change back to normalized xywh format for compatibility with usual tibava bboxes?
"track_id": str
}
"""


@AnalyserPluginManager.export("face_tracking")
class FaceTracker(
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
            inputs["bboxes"] as bbox_data,
            inputs["faces"] as faces_data,
            inputs["shots"] as shots_data,
        ):
            parameters["fps"] = 1 / bbox_data.bboxes[0].delta_time

            faces_by_frame = defaultdict(list)
            for face, bbox in zip(faces_data.faces, bbox_data.bboxes):
                if bbox.det_score >= 0.6 and bbox.h > 0.05:
                    faces_by_frame[bbox.time].append(
                        {
                            "id": face.id,
                            "frame": int(
                                bbox.time * parameters["fps"]
                            ),  # TODO maybe get frame id directly from somewhere (face.ref_id does not work)
                            "bbox": self.convert_bbox(bbox),
                            "conf": bbox.det_score,
                        }
                    )

            max_frame = len(faces_by_frame.keys())
            faces_list = [[] for _ in range(max_frame + 1)]
            for frame_index, face_list in enumerate(faces_by_frame.values()):
                faces_list[frame_index] = face_list

            # TODO change to bbox data type?
            with data_manager.create_data("AnnotationData") as track_data:
                for shot in shots_data.shots:
                    if shot.end - shot.start >= parameters.get("min_track"):
                        tracks = self.track_shot(
                            parameters,
                            faces_list[
                                int(shot.start * parameters["fps"]) : int(
                                    shot.end * parameters["fps"]
                                )
                            ],
                        )
                        for track in tracks:
                            annotation = Annotation(
                                start=float(track["frame"][0]) / parameters["fps"],
                                end=float(track["frame"][-1]) / parameters["fps"],
                                labels=[
                                    {
                                        "frames": track["frame"].tolist(),
                                        "bboxes": track["bbox"].tolist(),
                                        "track_id": track["track_id"],
                                    }
                                ],
                            )
                            track_data.annotations.append(annotation)

                return {
                    "track_data": track_data,
                }

    def bb_intersection_over_union(self, boxA: List[float], boxB: List[float]) -> float:
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        iou = interArea / float(boxAArea + boxBArea - interArea)
        return iou

    def convert_bbox(self, bbox) -> List[int]:
        _bbox = bbox.to_dict()
        x, y, w, h = _bbox["x"], _bbox["y"], _bbox["w"], _bbox["h"]
        return [x, y, x + w, y + h]

    def track_shot(
        self, params: Dict[str, Any], shotFaces: List[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        from scipy.interpolate import interp1d
        import uuid

        iouThres = 0.5
        tracks = []
        while True:
            track = []
            enhanced_track = {
                "frame": [],
                "bbox": [],
            }
            for frameFaces in shotFaces:
                for face in frameFaces:
                    if not track:
                        track.append(face)
                        frameFaces.remove(face)
                        enhanced_track["frame"].append(face["frame"])
                        enhanced_track["bbox"].append(face["bbox"])
                    elif face["frame"] - track[-1]["frame"] <= params["num_failed_det"]:
                        iou = self.bb_intersection_over_union(
                            face["bbox"], track[-1]["bbox"]
                        )
                        if iou > iouThres:
                            track.append(face)
                            frameFaces.remove(face)
                            enhanced_track["frame"].append(face["frame"])
                            enhanced_track["bbox"].append(face["bbox"])
                            continue
                    else:
                        break
            if not track:
                break
            elif len(track) > params["min_track"]:
                frameNum = np.array(enhanced_track["frame"])
                bboxes = np.array(enhanced_track["bbox"])
                frameI = np.arange(frameNum[0], frameNum[-1] + 1)
                bboxesI = []
                for ij in range(0, 4):
                    interpfn = interp1d(frameNum, bboxes[:, ij])
                    bboxesI.append(interpfn(frameI))
                bboxesI = np.stack(bboxesI, axis=1)
                if (
                    max(
                        np.mean(bboxesI[:, 2] - bboxesI[:, 0]),
                        np.mean(bboxesI[:, 3] - bboxesI[:, 1]),
                    )
                    > params["min_face_size"]
                ):
                    track_id = str(uuid.uuid4())
                    enhanced_track["track_id"] = track_id
                    enhanced_track["frame"] = frameI
                    enhanced_track["bbox"] = bboxesI

                    tracks.append(enhanced_track)
        return tracks
