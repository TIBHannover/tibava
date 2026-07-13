from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from tibava_data import (
    AnnotationData,
    Annotation,
    BboxesData,
    FacesData,
    ClusterData,
    ImageEmbeddings,
)

from tibava_data import DataManager, Data

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
    "shot_reverse_shot": AnnotationData,
}


@AnalyserPluginManager.export("movie_pattern_shot_reverse_shot")
class MoviePatternShotReverseShot(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.4",
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
            data_manager.create_data("AnnotationData") as shot_reverse_shot,
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

            shot_face_list = []

            for index, [shot_start, shot_end] in enumerate(shot_start_end):
                shot_faces = set()
                for face in faces.values():
                    if shot_start < face["time"] and face["time"] < shot_end:
                        shot_faces.add(face["cluster"])

                shot_face_list.append(list(shot_faces))

            srs_list = self.detect_shot_reverse_shot(shot_face_list)

            logging.error(shot_face_list)
            logging.error(shot_start_end)
            logging.error(srs_list)

            for shot in srs_list:
                logging.error(shot)

                start = shot_start_end[shot[0]][0]
                end = shot_start_end[shot[1]][1]
                shot_reverse_shot.annotations.append(
                    Annotation(start=start, end=end, labels=["Shot Reverse Shot"])
                )

        return {
            "shot_reverse_shot": shot_reverse_shot,
        }

    def detect_shot_reverse_shot(self, shots, min_length=4):
        results = []
        n = len(shots)
        i = 0

        while i < n - 2:
            # Check first two shots are single-person and different
            if len(shots[i]) == 1 and len(shots[i + 1]) == 1:
                A = shots[i][0]
                B = shots[i + 1][0]
                logging.error("##", A, B)
                if A != B:
                    start = i
                    expected = A
                    j = i

                    # Follow alternating pattern
                    while j < n and len(shots[j]) == 1:
                        current = shots[j][0]

                        if current != expected:
                            break

                        # Switch expected speaker
                        expected = B if expected == A else A
                        j += 1

                    length = j - start

                    if length >= min_length:
                        results.append((start, j, (A, B)))
                        i = j  # skip past this block
                        continue

            i += 1

        return results
