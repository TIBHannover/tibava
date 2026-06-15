from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import (
    AnnotationData,
    Annotation,
    BboxesData,
    FacesData,
    ClusterData,
    ImageEmbeddings,
)

from data import DataManager, Data

import logging
from typing import Callable, Dict

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {
    "min_length": 3,
}

requires = {
    "faces": FacesData,
    "bboxes": BboxesData,
    "cluster_data": ClusterData,
    "shots": AnnotationData,
    "embeddings": ImageEmbeddings,
}

provides = {
    "frameshare": AnnotationData,
}


# Some helper functions
def iou_xywh(box1, box2):
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    # Convert to (x1, y1, x2, y2)
    x1_max = x1 + w1
    y1_max = y1 + h1

    x2_max = x2 + w2
    y2_max = y2 + h2

    # Intersection rectangle
    inter_x1 = max(x1, x2)
    inter_y1 = max(y1, y2)
    inter_x2 = min(x1_max, x2_max)
    inter_y2 = min(y1_max, y2_max)

    # Compute intersection area
    inter_width = max(0, inter_x2 - inter_x1)
    inter_height = max(0, inter_y2 - inter_y1)
    inter_area = inter_width * inter_height

    # Areas of boxes
    area1 = w1 * h1
    area2 = w2 * h2

    # Union
    union_area = area1 + area2 - inter_area

    if union_area == 0:
        return 0

    return inter_area / union_area


def left_right_cls(bbox):
    l_iou = iou_xywh([bbox["x"], bbox["y"], bbox["w"], bbox["h"]], [0, 0, 0.5, 1.0])
    r_iou = iou_xywh([bbox["x"], bbox["y"], bbox["w"], bbox["h"]], [0.5, 0, 0.5, 1.0])
    return l_iou, r_iou


@AnalyserPluginManager.export("movie_pattern_frameshare")
class MoviePatternFrameshare(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.3",
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
        min_length = parameters.get("min_length")
        shot_start_end = []

        with (
            inputs["faces"] as faces_data,
            inputs["bboxes"] as bboxes_data,
            inputs["embeddings"] as embeddings_data,
            inputs["cluster_data"] as cluster_data,
            inputs["shots"] as shots_data,
            data_manager.create_data("AnnotationData") as frameshare,
        ):
            faces = {}
            for face in faces_data.faces:
                faces[face.id] = {}

            embeddings_map = {}
            for emb in embeddings_data.embeddings:
                embeddings_map[emb.id] = emb.ref_id
                faces[emb.ref_id]["time"] = emb.time

            for bbox in bboxes_data.bboxes:
                faces[bbox.ref_id]["bbox"] = bbox.to_dict()

            for i, cluster in enumerate(cluster_data.clusters):
                for id in cluster.embedding_ids:
                    faces[embeddings_map[id]]["cluster"] = i
            for x in shots_data.shots:
                shot_start_end.append([x.start, x.end])

            shot_face_left_right_list = []
            for index, [shot_start, shot_end] in enumerate(shot_start_end):
                shot_faces = set()
                shot_left_right = {}
                for face in faces.values():
                    if shot_start < face["time"] and face["time"] < shot_end:
                        l_r = left_right_cls(face["bbox"])
                        shot_faces.add(face["cluster"])

                        if face["cluster"] not in shot_left_right:
                            shot_left_right[face["cluster"]] = [0.0, 0.0]
                        shot_left_right[face["cluster"]][0] += l_r[0]
                        shot_left_right[face["cluster"]][1] += l_r[1]

                shot_results = []
                for shot_face in shot_faces:
                    shot_results.append(
                        {
                            "cluster": shot_face,
                            "lr": "left"
                            if shot_left_right[shot_face][0]
                            > shot_left_right[shot_face][1]
                            else "right",
                        }
                    )

                shot_face_left_right_list.append(shot_results)

            srso_list = self.detect_frameshare(shot_face_left_right_list, min_length)

            logging.error(shot_face_left_right_list)
            logging.error(shot_start_end)
            logging.error(srso_list)

            for shot in srso_list:
                logging.error(shot)

                start = shot_start_end[shot[0]][0]
                end = shot_start_end[shot[1]][1]
                frameshare.annotations.append(
                    Annotation(start=start, end=end, labels=["Frameshare"])
                )

        return {
            "frameshare": frameshare,
        }

    def detect_frameshare(self, shots, min_length=4):
        results = []
        n = len(shots)
        i = 0

        while i < n - 2:
            # Check first two shots are single-person and different
            if len(shots[i]) == 1 and len(shots[i + 1]) == 1:
                person_shot_1 = shots[i][0]["cluster"]
                person_shot_2 = shots[i + 1][0]["cluster"]

                person_shot_1_lr = shots[i][0]["lr"]
                person_shot_2_lr = shots[i + 1][0]["lr"]
                logging.error(
                    f"Checking shots {i} and {i + 1} with clusters {person_shot_1} and {person_shot_2} and lr {person_shot_1_lr} and {person_shot_2_lr}"
                )
                if (
                    # person_shot_1 != person_shot_2 and
                    person_shot_1_lr == person_shot_2_lr
                ):
                    start = i
                    expected = person_shot_1
                    expected_lr = person_shot_1_lr
                    j = i

                    # Follow alternating pattern
                    while j < n and len(shots[j]) == 1:
                        current = shots[j][0]["cluster"]
                        current_lr = shots[j][0]["lr"]

                        if current != expected or current_lr != expected_lr:
                            break

                        # Switch expected speaker
                        expected = (
                            person_shot_2
                            if expected == person_shot_1
                            else person_shot_1
                        )
                        expected_lr = (
                            person_shot_2_lr
                            if expected_lr == person_shot_1_lr
                            else person_shot_1_lr
                        )
                        j += 1

                    length = j - start

                    if length >= min_length:
                        results.append((start, j - 1, (person_shot_1, person_shot_2)))
                        i = j  # skip past this block
                        continue

            i += 1

        return results
