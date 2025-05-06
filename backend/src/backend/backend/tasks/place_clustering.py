from typing import Dict
import json
import os
import logging

from backend.models import (
    ClusterTimelineItem,
    ClusterItem,
    PluginRun,
    PluginRunResult,
    Timeline,
    TimelineSegment,
    TibavaUser,
    Video,
)

from backend.plugin_manager import PluginManager
from backend.utils import media_path_to_video

from ..utils.analyser_client import TaskAnalyserClient
from data import DataManager, Shot
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction
from django.conf import settings


@PluginManager.export_parser("place_clustering")
class PlaceClusteringParser(Parser):
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
            "encoder": {"parser": str, "default": "clip"},
            "shot_timeline_id": {"required": True},
            "max_samples_per_cluster": {"parser": int, "default": 30},
            "max_cluster": {"parser": int, "default": 50},
            "fps": {"parser": float, "default": 2.0},
        }


@PluginManager.export_plugin("place_clustering")
class PlaceClustering(Task):
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
        manager = DataManager(self.config["output_path"])
        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )

        video_id = self.upload_video(client, video)

        # get shots from timeline
        shots_id = None
        if parameters.get("shot_timeline_id"):
            shot_timeline_db = Timeline.objects.get(
                id=parameters.get("shot_timeline_id")
            )
            shot_timeline_segments = TimelineSegment.objects.filter(
                timeline=shot_timeline_db
            )

            shots = manager.create_data("ShotsData")
            with shots:
                for x in shot_timeline_segments:
                    shots.shots.append(Shot(start=x.start, end=x.end))
            shots_id = client.upload_data(shots)

        # sample frames from shots
        sample_result = self.run_analyser(
            client,
            "timeline_video_sampler",
            parameters={
                "middle_frame": True,
                "start_frame": False,
                "end_frame": False,
            },
            inputs={"input": video_id, "shots": shots_id},
            outputs=["output"],
            downloads=["output"],
        )
        if sample_result is None:
            raise Exception

        if plugin_run is not None:
            plugin_run.progress = 0.2
            plugin_run.save()

        # get embeddings for sampled frames within shots
        encoder_lut = {
            "clip": "clip_image_embedding",
            "places": "places_classifier",
        }
        encoder_plugin = encoder_lut[parameters.get("encoder").lower()]

        embeddings_result = self.run_analyser(
            client,
            encoder_plugin,
            parameters={},
            inputs={"video": sample_result[0]["output"]},
            outputs=["embeddings"],
            downloads=["embeddings"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.4
            plugin_run.save()

        # TODO aggregate embeddings per shot

        if plugin_run is not None:
            plugin_run.progress = 0.6
            plugin_run.save()

        # perform clustering
        clustering_lut = {
            "agglomerative": "clustering",
            "dbscan": "dbscanclustering",
        }
        clustering_method = clustering_lut[parameters.get("clustering_method").lower()]

        cluster_result = self.run_analyser(
            client,
            clustering_method,
            parameters={
                "cluster_threshold": parameters.get("cluster_threshold"),
                "max_samples_per_cluster": parameters.get("max_samples_per_cluster"),
            },
            inputs={
                "embeddings": embeddings_result[0]["embeddings"],
            },
            outputs=["cluster_data"],
            downloads=["cluster_data"],
        )

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
        with sample_result[1]["output"] as d:
            # extract thumbnails
            d.extract_all(manager)

        embedding_lut = {}
        with embeddings_result[1]["embeddings"] as d:
            for embedding in d.embeddings:
                embedding_lut[embedding.id] = embedding

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

                plugin_run_result_images_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=sample_result[1]["output"].id,
                    name="images",
                    type=PluginRunResult.TYPE_IMAGES,
                )

                plugin_run_result_features_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=embeddings_result[1]["embeddings"].id,
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
                    for embedding_id in cluster.embedding_ids:
                        image_id = embedding_lut[embedding_id].ref_id
                        image_path = os.path.join(
                            self.config.get("base_url"),
                            image_id[0:2],
                            image_id[2:4],
                            f"{image_id}.jpg",
                        )
                        _ = ClusterItem.objects.create(
                            cluster_timeline_item=cluster_timeline_item_db,
                            video=video,
                            embedding_id=embedding_id,
                            image_path=image_path,
                            plugin_run_result=plugin_run_result_db,
                            type=ClusterItem.TYPE_PLACE,
                            time=embedding_lut[embedding_id].time,
                            delta_time=embedding_lut[embedding_id].delta_time,
                            is_sample=embedding_id in cluster.sample_embedding_ids,
                        )

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [
                        plugin_run_result_db.id.hex,
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
