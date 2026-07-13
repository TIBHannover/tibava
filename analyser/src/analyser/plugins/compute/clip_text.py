import numpy as np
import uuid
from tibava_interface import analyser_pb2, data_pb2, common_pb2
from analyser.plugins import ComputePlugin, ComputePluginFactory, ComputePluginResult
from analyser.utils import image_from_proto, image_resize, image_crop


import logging

from typing import Union, List, Dict


default_config = {}


default_parameters = {}


@ComputePluginFactory.export("ClipTextEmbeddingFeature")
class ClipTextEmbeddingFeature(
    ComputePlugin, config=default_config, parameters=default_parameters, version="0.4"
):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_name = self.config.get("model", "xlm-roberta-base-ViT-B-32")
        self.pretrained = self.config.get("pretrained")
        self.embedding_size = self.config.get("embedding_size", 768)
        self.model = None

    def call(self, plugin_run: common_pb2.PluginRun):
        from sklearn.preprocessing import normalize
        import imageio.v3 as iio
        import torch
        import open_clip

        inputs, parameters = self.map_analyser_request_to_dict(plugin_run)

        device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.model is None:
            model, _, preprocess = open_clip.create_model_and_transforms(
                self.model_name,
                pretrained=self.pretrained,
                cache_dir="/models",
                device=device,
            )
            self.tokenizer = open_clip.get_tokenizer(self.model_name)
            self.model = model

        result = analyser_pb2.AnalyseReply()
        for entry in inputs["text"]:
            with torch.no_grad(), torch.amp.autocast(device):
                text = self.tokenizer(entry["content"])
                output = self.model.encode_text(text.to(device)).float()
            output = output / np.linalg.norm(np.asarray(output))
            output = output.flatten()
            data = data_pb2.Data(
                id=uuid.uuid4().hex,
                name="clip_embedding",
                feature=data_pb2.Feature(
                    type="clip_embedding", shape=output.shape, feature=output.tolist()
                ),
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
