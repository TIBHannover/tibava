import uuid
import logging
import numpy as np

from typing import Dict


from tibava_interface import analyser_pb2, data_pb2, common_pb2
from analyser.plugins import ComputePlugin, ComputePluginFactory


default_config = {
    "clip_image_plugin": "clip_image_xlm-roberta-base-vit-b-32_laion5b_s13b_b90k",
    "clip_text_plugin": "clip_text_xlm-roberta-base-vit-b-32_laion5b_s13b_b90k",
}


default_parameters = {"crop_size": [224, 224], "aggregation": "softmax"}


@ComputePluginFactory.export("ClipClassification")
class ClipClassification(
    ComputePlugin, config=default_config, parameters=default_parameters, version="0.4"
):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def call(self, plugin_run: common_pb2.PluginRun):
        import torch
        from sklearn.metrics.pairwise import cosine_similarity

        inputs, parameters = self.map_analyser_request_to_dict(plugin_run)

        image_embedding_request = self.map_dict_to_analyser_request(
            {"image": inputs["image"]}, parameters
        )

        image_embedding_result = self.inference_server_manager(
            self.compute_plugin_manager,
            self.config.get("clip_image_plugin"),
            request=image_embedding_request,
        )

        text_embedding_request = self.map_dict_to_analyser_request(
            {"text": inputs["text"]}, parameters
        )

        text_embedding_result = self.inference_server_manager(
            self.compute_plugin_manager,
            self.config.get("clip_text_plugin"),
            request=text_embedding_request,
        )

        text_embeddings = []
        for t in text_embedding_result.results:
            text_embeddings.append(
                np.asarray(t.result.feature.feature).reshape(t.result.feature.shape)
            )

        text_embeddings = np.stack(text_embeddings, 0)

        image_embeddings = []
        for i in image_embedding_result.results:
            image_embeddings.append(
                np.asarray(i.result.feature.feature).reshape(i.result.feature.shape)
            )

        image_embeddings = np.stack(image_embeddings, 0)

        if parameters.get("aggregation").lower() == "softmax":
            text_probs = torch.nn.functional.softmax(
                torch.from_numpy(100.0 * image_embeddings @ text_embeddings.T), dim=-1
            )

        if parameters.get("aggregation").lower() == "dot":
            text_probs = image_embeddings @ text_embeddings.T

        if parameters.get("aggregation").lower() == "cosine":
            text_probs = cosine_similarity(image_embeddings, text_embeddings)

        result = analyser_pb2.AnalyseReply()

        for i, _ in enumerate(inputs["image"]):
            concepts = []

            for j, concept in enumerate(inputs["text"]):
                concepts.append(
                    data_pb2.Concept(
                        concept=concept["content"], prob=text_probs[i, j].item()
                    )
                )

            data = data_pb2.Data(
                id=uuid.uuid4().hex,
                name="clip_embedding",
                classifier=data_pb2.ClassifierResult(concepts=concepts),
            )

            result.results.append(
                common_pb2.PluginResult(
                    plugin=self.instance_name,
                    type=self.name(),
                    version=self.version(),
                    result=data,
                )
            )

        return result
