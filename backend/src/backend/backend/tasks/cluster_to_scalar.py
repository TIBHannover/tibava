from typing import Dict
import logging
import numpy as np

from backend.models import (
    ClusterTimelineItem,
    PluginRun,
    PluginRunResult,
    Video,
    TibavaUser,
    Timeline,
)

from backend.plugin_manager import PluginManager

from ..utils.analyser_client import TaskAnalyserClient
from data import DataManager, ImageEmbedding
from backend.utils.parser import Parser
from backend.utils.task import Task
from django.db import transaction
from django.conf import settings


logger = logging.getLogger(__name__)


@PluginManager.export_parser("cluster_to_scalar")
class ClusterToScalarParser(Parser):
    def __init__(self):
        self.valid_parameter = {
            "timeline": {"parser": str, "default": "Cluster Similarity"},
            "cluster_timeline_item_id": {"parser": str},
        }


@PluginManager.export_plugin("cluster_to_scalar")
class ClusterToScalar(Task):
    def __init__(self):
        self.config = {
            "output_path": "/predictions/",
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

        cti = ClusterTimelineItem.objects.get(
            id=parameters.get("cluster_timeline_item_id")
        )

        embedding_result = cti.plugin_run.results.filter(
            type=PluginRunResult.TYPE_IMAGE_EMBEDDINGS
        ).first()

        # load embeddings and compute mean of all non deleted embeddings from a cluster
        with manager.load(embedding_result.data_id) as embedding_data:
            embed_map = {embed.id: embed for embed in embedding_data.embeddings}
            cluster_feature = [
                embed_map[emb_id].embedding
                for emb_id in cti.items.filter(is_sample=True).values_list(
                    "embedding_id", flat=True
                )
            ]

            query_feature = np.mean(cluster_feature, axis=0)

        query_image_feature = manager.create_data("ImageEmbeddings")
        with query_image_feature:
            query_image_feature.embeddings.append(
                ImageEmbedding(
                    embedding=query_feature,
                    time=0,
                    delta_time=1,
                )
            )

        client = TaskAnalyserClient(
            host=self.config["analyser_host"],
            port=self.config["analyser_port"],
            plugin_run_db=plugin_run,
            manager=manager,
        )
        query_image_feature_id = client.upload_data(query_image_feature)

        # upload all data
        video_id = self.upload_video(client, video)

        # face detection on video
        video_facedetection = self.run_analyser(
            client,
            "insightface_video_detector_torch",
            parameters={
                "fps": parameters.get("fps"),
            },
            inputs={"video": video_id},
            outputs=["kpss", "faces"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.25
            plugin_run.save()

        if video_facedetection is None:
            raise Exception

        video_feature_result = self.run_analyser(
            client,
            "insightface_video_feature_extractor",
            inputs={"video": video_id, "kpss": video_facedetection[0]["kpss"]},
            outputs=["features"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.5
            plugin_run.save()

        if video_feature_result is None:
            raise Exception

        result = self.run_analyser(
            client,
            "cosine_similarity",
            parameters={
                "normalize": 1,
                "index": parameters.get("index"),
            },
            inputs={
                "target_features": video_feature_result[0]["features"],
                "query_features": query_image_feature_id,
            },
            outputs=["probs"],
        )

        if plugin_run is not None:
            plugin_run.progress = 0.75
            plugin_run.save()

        if result is None:
            raise Exception

        aggregated_result = self.run_analyser(
            client,
            "aggregate_scalar_per_time",
            inputs={"scalar": result[0]["probs"]},
            downloads=["aggregated_scalar"],
        )

        if aggregated_result is None:
            raise Exception

        if dry_run or plugin_run is None:
            logging.warning("dry_run or plugin_run is None")
            return {}

        with transaction.atomic():
            with aggregated_result[1]["aggregated_scalar"] as data:
                plugin_run_result_db = PluginRunResult.objects.create(
                    plugin_run=plugin_run,
                    data_id=data.id,
                    name="face_identification",
                    type=PluginRunResult.TYPE_SCALAR,
                )
                timeline_db = Timeline.objects.create(
                    video=video,
                    name=parameters.get("timeline"),
                    type=Timeline.TYPE_PLUGIN_RESULT,
                    plugin_run_result=plugin_run_result_db,
                    visualization=Timeline.VISUALIZATION_SCALAR_COLOR,
                )

                return {
                    "plugin_run": plugin_run.id.hex,
                    "plugin_run_results": [plugin_run_result_db.id.hex],
                    "timelines": {"annotations": timeline_db},
                    "data": {
                        "annotations": aggregated_result[1]["aggregated_scalar"].id
                    },
                }
