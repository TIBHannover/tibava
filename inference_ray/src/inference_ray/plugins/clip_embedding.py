import os
import logging
import numpy as np

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import (
    VideoData,
    ScalarData,
    ImageEmbedding,
    TextEmbedding,
    ImageEmbeddings,
    TextEmbeddings,
    ListData,
)
from data import DataManager, Data

from typing import Callable, Optional, Dict

# from inference import InferenceServer
from utils import VideoDecoder
from utils.imageops import image_resize, image_crop, image_pad


class ImagePreprozessorWrapper:
    def __init__(self, clip, format) -> None:
        super().__init__()
        self.mean = None or getattr(clip.visual, "image_mean", None)
        self.std = None or getattr(clip.visual, "image_std", None)
        self.image_size = clip.visual.image_size
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
    "data_dir": "/data/",
}


img_embd_parameters = {
    "fps": 2,
    "crop_size": [224, 224],
}


img_embd_requires = {
    "video": VideoData,
}

img_embd_provides = {
    "embeddings": ImageEmbeddings,
}


@AnalyserPluginManager.export("clip_image_embedding")
class ClipImageEmbedding(
    AnalyserPlugin,
    config=default_config,
    parameters=img_embd_parameters,
    version="0.1",
    requires=img_embd_requires,
    provides=img_embd_provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        # self.server = InferenceServer.build(inference_config.get("type"), inference_config.get("params", {}))
        # self.
        self.model_name = config.get("model", "xlm-roberta-base-ViT-B-32")
        self.pretrained = config.get("pretrained", "xlm-roberta-base-ViT-B-32")
        self.model = None

    def image_resize_crop(self, img, resize_size, crop_size):
        converted = image_resize(image_pad(img), size=crop_size)
        return converted

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        from sklearn.preprocessing import normalize
        import imageio
        import torch
        import open_clip

        device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.model is None:
            model, _, preprocess = open_clip.create_model_and_transforms(
                self.model_name,
                pretrained=self.pretrained,
                cache_dir="/models",
                device=device,
            )

            self.model = model.visual
            self.preprocess = ImagePreprozessorWrapper(model, format=torch.float32)

        with (
            inputs["video"] as input_data,
            data_manager.create_data("ImageEmbeddings") as output_data,
        ):
            with input_data(fps=parameters.get("fps")) as input_iterator:
                for i, frame in enumerate(input_iterator):
                    # self.update_callbacks(
                    #     callbacks, progress=float(i / len(input_iterator))
                    # )

                    img = frame.get("frame")
                    img = self.image_resize_crop(
                        img, parameters.get("resize_size"), parameters.get("crop_size")
                    )
                    img = self.preprocess(img).to(device)

                    with torch.no_grad(), torch.cuda.amp.autocast():
                        embedding = self.model(img)
                        embedding = torch.nn.functional.normalize(embedding, dim=-1)
                    embedding = embedding.cpu().detach()
                    output_data.embeddings.append(
                        ImageEmbedding(
                            embedding=normalize(embedding),
                            time=frame.get("time"),
                            ref_id=frame.get("id"),
                            delta_time=1 / parameters.get("fps"),
                        )
                    )

                self.update_callbacks(callbacks, progress=1.0)
            return {"embeddings": output_data}


text_embd_parameters = {
    "search_term": "",
}

text_embd_requires = {}

text_embd_provides = {
    "embeddings": TextEmbeddings,
}


@AnalyserPluginManager.export("clip_text_embedding")
class ClipTextEmbedding(
    AnalyserPlugin,
    config=default_config,
    parameters=text_embd_parameters,
    version="0.1",
    requires=text_embd_requires,
    provides=text_embd_provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        self.model_name = config.get("model", "xlm-roberta-base-ViT-B-32")
        self.pretrained = config.get("pretrained", "xlm-roberta-base-ViT-B-32")
        self.model = None

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        from sklearn.preprocessing import normalize
        import torch
        import open_clip

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
        with data_manager.create_data("TextEmbeddings") as output_data:
            # text = self.preprocess(parameters["search_term"])

            with torch.no_grad(), torch.cuda.amp.autocast():
                text = self.tokenizer([parameters["search_term"]])
                result = self.model.encode_text(text.to(device))
            result = result.cpu().detach().numpy()
            output_data.embeddings.append(
                TextEmbedding(text=parameters["search_term"], embedding=result[0])
            )
            self.update_callbacks(callbacks, progress=1.0)
            return {"embeddings": output_data}


prob_parameters = {"search_term": "", "softmax": False}

prob_requires = {
    "embeddings": ImageEmbeddings,
    "concepts": ListData,
}

prob_provides = {
    "probs": ListData,
}


@AnalyserPluginManager.export("clip_ontology_probs")
class ClipOntologyProbs(
    AnalyserPlugin,
    config=default_config,
    parameters=prob_parameters,
    version="0.53",
    requires=prob_requires,
    provides=prob_provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        self.model_name = config.get("model", "xlm-roberta-base-ViT-B-32")
        self.pretrained = config.get("pretrained", "xlm-roberta-base-ViT-B-32")
        self.model = None

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import scipy
        from sklearn.preprocessing import normalize
        import torch
        import open_clip

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

        with (
            inputs["embeddings"] as input_data,
            inputs["concepts"] as concepts,
            data_manager.create_data("ListData") as output_data,
        ):
            probs = []
            time = []
            delta_time = None
            text_embeddings = []
            indexes = []
            for index, concept in concepts:
                indexes.append(index)
                # print(concept.text, flush=True)
                with concept:
                    with torch.no_grad(), torch.cuda.amp.autocast():
                        text = self.tokenizer([concept.text])
                        result = self.model.encode_text(text.to(device))
                    result = result.cpu().detach().numpy()

                    text_embedding = normalize(result)
                    text_embeddings.append(text_embedding)
            # pos_embeddings = []
            # for t in openai_imagenet_template:
            #     pos_text = t(parameters["search_term"])
            #     result = self.server({"data": pos_text}, ["embedding"])

            #     text_embedding = normalize(result["embedding"])
            #     pos_embeddings.append(text_embedding)
            # pos_embeddings = np.concatenate(pos_embeddings, axis=0)
            # pos_embeddings = np.mean(pos_embeddings, axis=0, keepdims=True)

            # text_embedding = normalize(pos_embeddings)

            # neg_text = "Not " + parameters["search_term"]
            # neg_result = self.server({"data": neg_text}, ["embedding"])

            # neg_text_embedding = normalize(neg_result["embedding"])

            text_embedding = np.concatenate([text_embeddings], axis=0)
            for embedding in input_data.embeddings:
                result = 100 * text_embedding @ embedding.embedding.T
                prob = scipy.special.softmax(result, axis=0)

                # sim = 1 - spatial.distance.cosine(embedding.embedding, text_embedding)
                probs.append(prob)
                time.append(embedding.time)
                delta_time = embedding.delta_time

            y = np.array(probs)
            self.update_callbacks(callbacks, progress=1.0)
            for i, (index, concept) in enumerate(zip(indexes, concepts)):
                with output_data.create_data("ScalarData", index) as scalar_data:
                    scalar_data.y = np.asarray(y[:, i, 0, 0])
                    scalar_data.time = time
                    scalar_data.delta_time = delta_time
            return {"probs": output_data}


prob_parameters = {"search_term": "", "softmax": False}

prob_requires = {
    "embeddings": ImageEmbeddings,
}

prob_provides = {
    "probs": ScalarData,
}


@AnalyserPluginManager.export("clip_probs")
class ClipProbs(
    AnalyserPlugin,
    config=default_config,
    parameters=prob_parameters,
    version="0.53",
    requires=prob_requires,
    provides=prob_provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        self.model_name = config.get("model", "xlm-roberta-base-ViT-B-32")
        self.pretrained = config.get("pretrained", "xlm-roberta-base-ViT-B-32")
        self.model = None

        # inference_config = self.config.get("inference", None)
        # self.server = InferenceServer.build(inference_config.get("type"), inference_config.get("params", {}))

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import scipy
        from sklearn.preprocessing import normalize
        import torch
        import open_clip

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

        with (
            inputs["embeddings"] as input_data,
            data_manager.create_data("ScalarData") as output_data,
        ):
            probs = []
            time = []
            delta_time = None
            pos_embeddings = []
            for t in openai_imagenet_template:
                pos_text = t(parameters["search_term"])

                with torch.no_grad(), torch.cuda.amp.autocast():
                    text = self.tokenizer([pos_text])
                    result = self.model.encode_text(text.to(device))
                result = result.cpu().detach().numpy()
                # result = self.server({"data": pos_text}, ["embedding"])

                text_embedding = normalize(result)
                pos_embeddings.append(text_embedding)
            pos_embeddings = np.concatenate(pos_embeddings, axis=0)
            pos_embeddings = np.mean(pos_embeddings, axis=0, keepdims=True)

            text_embedding = normalize(pos_embeddings)

            neg_text = "Not " + parameters["search_term"]
            # neg_result = self.server({"data": neg_text}, ["embedding"])

            with torch.no_grad(), torch.cuda.amp.autocast():
                text = self.tokenizer([neg_text])
                result = self.model.encode_text(text.to(device))
            result = result.cpu().detach().numpy()
            # result = self.server({"data": pos_text}, ["embedding"])

            neg_text_embedding = normalize(result)

            # neg_text_embedding = normalize(neg_result["embedding"])

            text_embedding = np.concatenate(
                [text_embedding, neg_text_embedding], axis=0
            )
            for embedding in input_data.embeddings:
                if parameters["softmax"]:
                    result = 100 * text_embedding @ embedding.embedding.T
                    prob = scipy.special.softmax(result, axis=0)
                else:
                    prob = text_embedding @ embedding.embedding.T

                # sim = 1 - spatial.distance.cosine(embedding.embedding, text_embedding)
                probs.append(prob[0, 0])
                time.append(embedding.time)
                delta_time = embedding.delta_time

            y = np.array(probs)

            self.update_callbacks(callbacks, progress=1.0)
            output_data.y = y
            output_data.time = time
            output_data.delta_time = delta_time
            output_data.name = "image_text_similarities"
            return {"probs": output_data}


openai_imagenet_template = [
    lambda c: f"a bad photo of a {c}.",
    lambda c: f"a photo of many {c}.",
    lambda c: f"a sculpture of a {c}.",
    lambda c: f"a photo of the hard to see {c}.",
    lambda c: f"a low resolution photo of the {c}.",
    lambda c: f"a rendering of a {c}.",
    lambda c: f"graffiti of a {c}.",
    lambda c: f"a bad photo of the {c}.",
    lambda c: f"a cropped photo of the {c}.",
    lambda c: f"a tattoo of a {c}.",
    lambda c: f"the embroidered {c}.",
    lambda c: f"a photo of a hard to see {c}.",
    lambda c: f"a bright photo of a {c}.",
    lambda c: f"a photo of a clean {c}.",
    lambda c: f"a photo of a dirty {c}.",
    lambda c: f"a dark photo of the {c}.",
    lambda c: f"a drawing of a {c}.",
    lambda c: f"a photo of my {c}.",
    lambda c: f"the plastic {c}.",
    lambda c: f"a photo of the cool {c}.",
    lambda c: f"a close-up photo of a {c}.",
    lambda c: f"a black and white photo of the {c}.",
    lambda c: f"a painting of the {c}.",
    lambda c: f"a painting of a {c}.",
    lambda c: f"a pixelated photo of the {c}.",
    lambda c: f"a sculpture of the {c}.",
    lambda c: f"a bright photo of the {c}.",
    lambda c: f"a cropped photo of a {c}.",
    lambda c: f"a plastic {c}.",
    lambda c: f"a photo of the dirty {c}.",
    lambda c: f"a jpeg corrupted photo of a {c}.",
    lambda c: f"a blurry photo of the {c}.",
    lambda c: f"a photo of the {c}.",
    lambda c: f"a good photo of the {c}.",
    lambda c: f"a rendering of the {c}.",
    lambda c: f"a {c} in a video game.",
    lambda c: f"a photo of one {c}.",
    lambda c: f"a doodle of a {c}.",
    lambda c: f"a close-up photo of the {c}.",
    lambda c: f"a photo of a {c}.",
    lambda c: f"the origami {c}.",
    lambda c: f"the {c} in a video game.",
    lambda c: f"a sketch of a {c}.",
    lambda c: f"a doodle of the {c}.",
    lambda c: f"a origami {c}.",
    lambda c: f"a low resolution photo of a {c}.",
    lambda c: f"the toy {c}.",
    lambda c: f"a rendition of the {c}.",
    lambda c: f"a photo of the clean {c}.",
    lambda c: f"a photo of a large {c}.",
    lambda c: f"a rendition of a {c}.",
    lambda c: f"a photo of a nice {c}.",
    lambda c: f"a photo of a weird {c}.",
    lambda c: f"a blurry photo of a {c}.",
    lambda c: f"a cartoon {c}.",
    lambda c: f"art of a {c}.",
    lambda c: f"a sketch of the {c}.",
    lambda c: f"a embroidered {c}.",
    lambda c: f"a pixelated photo of a {c}.",
    lambda c: f"itap of the {c}.",
    lambda c: f"a jpeg corrupted photo of the {c}.",
    lambda c: f"a good photo of a {c}.",
    lambda c: f"a plushie {c}.",
    lambda c: f"a photo of the nice {c}.",
    lambda c: f"a photo of the small {c}.",
    lambda c: f"a photo of the weird {c}.",
    lambda c: f"the cartoon {c}.",
    lambda c: f"art of the {c}.",
    lambda c: f"a drawing of the {c}.",
    lambda c: f"a photo of the large {c}.",
    lambda c: f"a black and white photo of a {c}.",
    lambda c: f"the plushie {c}.",
    lambda c: f"a dark photo of a {c}.",
    lambda c: f"itap of a {c}.",
    lambda c: f"graffiti of the {c}.",
    lambda c: f"a toy {c}.",
    lambda c: f"itap of my {c}.",
    lambda c: f"a photo of a cool {c}.",
    lambda c: f"a photo of a small {c}.",
    lambda c: f"a tattoo of the {c}.",
]
