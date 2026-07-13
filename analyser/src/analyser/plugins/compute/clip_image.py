import uuid
import logging

import numpy as np

from typing import Dict


from tibava_interface import analyser_pb2, data_pb2, common_pb2
from analyser.plugins import ComputePlugin, ComputePluginFactory, ComputePluginResult
from analyser.utils import image_from_proto, image_resize, image_crop, image_pad


class ImagePreprozessorWrapper:
    def __init__(self, clip, format) -> None:
        super().__init__()
        self.mean = None or getattr(clip.visual, "image_mean", None)
        self.std = None or getattr(clip.visual, "image_std", None)
        self.image_size = clip.visual.image_size
        print(self.image_size)
        self.transform = self.image_transform()
        self.format = format

    def image_transform(self):
        OPENAI_DATASET_MEAN = (0.48145466, 0.4578275, 0.40821073)
        OPENAI_DATASET_STD = (0.26862954, 0.26130258, 0.27577711)

        from torchvision.transforms import (
            Normalize,
            Compose,
            InterpolationMode,
            ToTensor,
            Resize,
            CenterCrop,
            ToPILImage,
        )

        image_size = self.image_size

        mean = self.mean or OPENAI_DATASET_MEAN
        if not isinstance(mean, (list, tuple)):
            mean = (mean,) * 3

        std = self.std or OPENAI_DATASET_STD
        if not isinstance(std, (list, tuple)):
            std = (std,) * 3

        if isinstance(image_size, (list, tuple)) and image_size[0] == image_size[1]:
            # for square size, pass size as int so that Resize() uses aspect preserving shortest edge
            image_size = image_size[0]

        transforms = [
            ToPILImage(),
            Resize(image_size, interpolation=InterpolationMode.BICUBIC),
            CenterCrop(image_size),
            ToTensor(),
            Normalize(mean=mean, std=std),
        ]
        return Compose(transforms)

    def __call__(self, image):
        import torch

        # print(image)
        # print(image.shape)
        # print(image.dtype)
        # print(type(image))
        if isinstance(image, torch.Tensor):
            image = image.cpu().numpy().astype(np.uint8)
        image = image.astype(np.uint8)
        # print(type(image))
        # if isinstance(image, torch.Tensor):
        #     print("#####")
        #     print(image)
        #     print(image.shape)
        #     print(image.dtype)
        result = []
        if len(image.shape) == 4:
            for x in range(image.shape[0]):
                result.append(self.transform(image[x]))

        else:
            result.append(self.transform(image))

        return torch.stack(result, axis=0).to(self.format)


default_config = {
    "multicrop": True,
    "max_dim": None,
    "min_dim": 224,
}


default_config = {
    "multicrop": True,
    "max_dim": None,
    "min_dim": 224,
}

default_parameters = {
    "crop_size": [224, 224],
}


@ComputePluginFactory.export("ClipImageEmbeddingFeature")
class ClipImageEmbeddingFeature(
    ComputePlugin, config=default_config, parameters=default_parameters, version="0.4"
):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.max_dim = self.config["max_dim"]
        self.min_dim = self.config["min_dim"]

        self.model_name = self.config.get("model", "xlm-roberta-base-ViT-B-32")
        self.pretrained = self.config.get("pretrained")
        self.embedding_size = self.config.get("embedding_size", 768)
        self.model = None

    def image_resize_crop(self, img, resize_size, crop_size):
        converted = image_resize(image_pad(img), size=crop_size)
        return converted

    def init_model(self):
        if self.model is None:
            from sklearn.preprocessing import normalize
            import imageio.v3 as iio
            import torch
            import open_clip

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logging.info(f"Load on device {device}")
            model, _, preprocess = open_clip.create_model_and_transforms(
                self.model_name,
                pretrained=self.pretrained,
                cache_dir="/models",
                device=device,
            )

            self.model = model.visual
            self.preprocess = ImagePreprozessorWrapper(model, format=torch.float32)

    def call(self, plugin_run: common_pb2.PluginRun):
        from sklearn.preprocessing import normalize
        import imageio.v3 as iio
        import torch
        import open_clip

        inputs, parameters = self.map_analyser_request_to_dict(plugin_run)

        device = "cuda" if torch.cuda.is_available() else "cpu"

        self.init_model()

        result = analyser_pb2.AnalyseReply()
        for entry in inputs["image"]:
            # image = image_from_proto(entry)
            image = iio.imread(entry["content"])

            # image = image_resize(image, max_dim=self.max_dim, min_dim=self.min_dim)
            # image = image_crop(image, [224, 224])

            image = self.image_resize_crop(
                image, parameters.get("resize_size"), parameters.get("crop_size")
            )
            image = self.preprocess(image).to(device)

            with torch.no_grad(), torch.amp.autocast(device):
                embedding = self.model(image)
                embedding = torch.nn.functional.normalize(embedding, dim=-1).float()
            embedding = embedding.cpu().detach()
            # normalize
            output = embedding / np.linalg.norm(np.asarray(embedding))
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
