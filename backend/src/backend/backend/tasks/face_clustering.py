from typing import Dict, List
import imageio.v3 as iio
import json
import os
import logging

from backend.models import (
    ClusterTimelineItem,
    ClusterItem,
    PluginRun,
    PluginRunResult,
    Video,
    TibavaUser,
)

from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from ..utils.analyser_client import TaskAnalyserClient
from data import DataManager
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("face_clustering")
class FaceClusteringParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            # clustering-specific params
            "clustering_method": {"parser": str, "default": "DBScan"},
            "cluster_threshold": {
                "parser": float,
                "default": 0.5,
            },  # agglomerative, dbscan
            "metric": {"parser": str, "default": "cosine"},  # dbscan
            # other params
            "max_samples_per_cluster": {"parser": int, "default": 30},
            "max_cluster": {"parser": int, "default": 50},
            "min_face_height": {"parser": float, "default": 0.1},
            "fps": {"parser": float, "default": 2.0},
        }


@PluginManager.export_plugin("face_clustering")
class FaceClustering(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
            "base_url": settings.THUMBNAIL_URL,
            "analyser_host": settings.GRPC_HOST,
            "analyser_port": settings.GRPC_PORT,
        }

    def __call__(
        self,
        parameters: Dict,
        video: Video = None,
        user: TibavaUser = None,
        plugin_run: PluginRun = None,
        dry_run: bool = False,
        **kwargs,
    ):
        # Debug
        # parameters["fps"] = 0.05

        manager = DataManager(self.config["output_path"])
        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )

        # face detector
        video_data_id = self.upload_video(client, video)
        facedetector_result = self.run_analyser(
            client,
            "insightface_video_detector_torch",
            parameters={
                "fps": parameters.get("fps"),
            },
            inputs={"video": video_data_id},
            outputs=["images", "kpss", "faces", "bboxes"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.2
            plugin_run.save()

        if facedetector_result is None:
            raise Exception

        face_size_filter_result = self.run_analyser(
            client,
            "face_size_filter",
            parameters={
                "min_face_height": parameters.get("min_face_height"),
            },
            inputs=facedetector_result[0],
            outputs=["images", "kpss", "faces", "bboxes"],
            downloads=["images", "faces"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.4
            plugin_run.save()

        if face_size_filter_result is None:
            raise Exception

        # create image embeddings
        image_feature_result = self.run_analyser(
            client,
            "insightface_video_feature_extractor",
            inputs={
                "video": video_data_id,
                "kpss": face_size_filter_result[0]["kpss"],
                "faces": face_size_filter_result[0]["faces"],
            },
            outputs=["features"],
            downloads=["features"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.6
            plugin_run.save()

        if image_feature_result is None:
            raise Exception

        # cluster faces
        if parameters.get("clustering_method").lower() == "agglomerative":
            cluster_result = self.run_analyser(
                client,
                "clustering",
                parameters={
                    "cluster_threshold": parameters.get("cluster_threshold"),
                    "max_samples_per_cluster": parameters.get(
                        "max_samples_per_cluster"
                    ),
                },
                inputs={
                    "embeddings": image_feature_result[0]["features"],
                },
                outputs=["cluster_data"],
                downloads=["cluster_data"],
            )
        elif parameters.get("clustering_method").lower() == "dbscan":
            cluster_result = self.run_analyser(
                client,
                "dbscanclustering",
                parameters={
                    "cluster_threshold": parameters.get("cluster_threshold"),
                    "metric": parameters.get("metric"),
                    "max_samples_per_cluster": parameters.get(
                        "max_samples_per_cluster"
                    ),
                },
                inputs={
                    "embeddings": image_feature_result[0]["features"],
                },
                outputs=["cluster_data"],
                downloads=["cluster_data"],
            )
        else:
            raise Exception

        if plugin_run is not None:
            plugin_run.progress = 0.8
            plugin_run.save()

        if cluster_result is None:
            raise Exception

        # cluster filter top k clusters
        cluster_filter_result = self.run_analyser(
            client,
            "cluster_size_filter",
            parameters={
                "max_cluster": parameters.get("max_cluster"),
            },
            inputs={
                "clusters": cluster_result[0]["cluster_data"],
            },
            downloads=["clusters"],
        )

        if cluster_filter_result is None:
            raise Exception

        # save thumbnails
        with face_size_filter_result[1]["images"] as d:
            # extract thumbnails
            d.extract_all(manager)

        embedding_face_lut = {}
        with image_feature_result[1]["features"] as d:
            for embedding in d.embeddings:
                embedding_face_lut[embedding.id] = embedding.ref_id

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with cluster_filter_result[1]["clusters"] as data:
                # save cluster results
                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=data.id,
                    name="clustering",
                    type=PluginRunResult.TYPE_CLUSTER,
                )

                plugin_run_result_faces_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=face_size_filter_result[1]["faces"].id,
                    name="faces",
                    type=PluginRunResult.TYPE_FACE,
                )

                plugin_run_result_images_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=face_size_filter_result[1]["images"].id,
                    name="images",
                    type=PluginRunResult.TYPE_IMAGES,
                )

                plugin_run_result_features_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=image_feature_result[1]["features"].id,
                    name="features",
                    type=PluginRunResult.TYPE_IMAGE_EMBEDDINGS,
                )

                # create a cti for every detected cluster
                for cluster_index, cluster in enumerate(data.clusters):
                    cluster_timeline_item_db = ClusterTimelineItem.objects.create(
                        video=video,
                        cluster_id=cluster.id,
                        name=f"Cluster {cluster_index+1}",
                        plugin_run=plugin_run,
                    )

                    # create a face db item for every detected face
                    for face_index, embedding_id in enumerate(cluster.embedding_ids):
                        image = [
                            f
                            for f in face_size_filter_result[1]["images"].images
                            if f.ref_id == embedding_face_lut[embedding_id]
                        ][0]
                        image_path = os.path.join(
                            self.config.get("base_url"),
                            image.id[0:2],
                            image.id[2:4],
                            f"{image.id}.{image.ext}",
                        )
                        _ = ClusterItem.objects.create(
                            cluster_timeline_item=cluster_timeline_item_db,
                            video=video,
                            # plugin_item_ref=embedding_face_lut[embedding_id],
                            embedding_id=embedding_id,
                            image_path=image_path,
                            plugin_run_result=plugin_run_result_db,
                            type=ClusterItem.TYPE_FACE,
                            time=image.time,
                            delta_time=image.delta_time,
                            is_sample=embedding_id in cluster.sample_embedding_ids,
                        )

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [
                        plugin_run_result_db.id.hex,
                        plugin_run_result_faces_db.id.hex,
                        plugin_run_result_images_db.id.hex,
                        plugin_run_result_features_db.id.hex,
                    ],
                    "timelines": {},
                    "data": {"clusters": cluster_filter_result[1]["clusters"].id},
                }

    def get_results(self, analyse):
        try:
            results = json.loads(bytes(analyse.results).decode("utf-8"))
            results = [
                {**x, "url": self.config.get("base_url") + f"{analyse.id}/{x['path']}"}
                for x in results
            ]

            return results
        except:
            return []
