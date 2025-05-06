import os
import logging
import numpy as np

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import (
    VideoData,
    Annotation,
    AnnotationData,
    ImageEmbedding,
    ImageEmbeddings,
    ImagesData,
    ShotsData,
)
from data import DataManager, Data

from typing import Callable, Optional, Dict, Union

# from inference import InferenceServer
from utils import VideoDecoder
from utils.imageops import image_resize, image_crop, image_pad

# from PIL import Image

default_config = {
    "data_dir": "/data/",
}


img_embd_parameters = {
    "fps": None,
    "crop_size": [224, 224],
}


img_embd_requires = {
    "input": Union[VideoData, ImagesData],
}

img_embd_provides = {
    "embeddings": ImageEmbeddings,
}


@AnalyserPluginManager.export("blip_image_embedding")
class BlipImageEmbedding(
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
        self.model_name = config.get("model", "Salesforce/instructblip-flan-t5-xl")
        self.model = None

    def model_init(self):
        import torch
        from transformers import (
            InstructBlipProcessor,
            InstructBlipForConditionalGeneration,
        )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.device == "cuda":
            self.dtype = torch.bfloat16
            self.model = InstructBlipForConditionalGeneration.from_pretrained(
                self.model_name,
                device_map="auto",
                load_in_8bit=True,
                torch_dtype=self.dtype,
            ).vision_model
        else:
            self.dtype = torch.float32
            self.model = InstructBlipForConditionalGeneration.from_pretrained(
                self.model_name
            ).vision_model
        self.processor = InstructBlipProcessor.from_pretrained(self.model_name)
        # self.model.to(self.device)

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

        device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.model is None:
            self.model_init()

        with (
            inputs["input"] as input_data,
            data_manager.create_data("ImageEmbeddings") as output_data,
        ):
            with input_data() as input_iterator:
                for i, frame in enumerate(input_iterator):
                    self.update_callbacks(callbacks, progress=i / len(input_iterator))

                    img = frame.get("frame")
                    img = self.processor(images=img, return_tensors="pt").to(
                        device, dtype=self.dtype
                    )

                    with torch.no_grad(), torch.cuda.amp.autocast():
                        embedding = self.model(
                            img["pixel_values"], return_dict=True
                        ).last_hidden_state
                        # embedding = self.model(img)
                        # embedding = torch.nn.functional.normalize(embedding, dim=-1)
                    embedding = embedding.cpu().detach()

                    if frame.get("delta_time"):
                        delta_time = frame.get("delta_time")
                    elif parameters.get("fps"):
                        delta_time = 1 / parameters.get("fps")
                    output_data.embeddings.append(
                        ImageEmbedding(
                            embedding=embedding,
                            time=frame.get("time"),
                            delta_time=delta_time,
                        )
                    )

                self.update_callbacks(callbacks, progress=1.0)
            return {"embeddings": output_data}


default_config = {
    "data_dir": "/data/",
}


prob_parameters = {"query_term": ""}


img_embd_requires = {
    "embeddings": ImageEmbeddings,
    "shots": ShotsData,
}

img_embd_provides = {
    "annotations": AnnotationData,
}


@AnalyserPluginManager.export("blip_vqa")
class BlipVQA(
    AnalyserPlugin,
    config=default_config,
    parameters=prob_parameters,
    version="0.2",
    requires=img_embd_requires,
    provides=img_embd_provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        # self.server = InferenceServer.build(inference_config.get("type"), inference_config.get("params", {}))
        # self.
        self.model_name = config.get("model", "Salesforce/instructblip-flan-t5-xl")
        self.model = None

    def model_init(self):
        import torch
        from transformers import (
            InstructBlipProcessor,
            InstructBlipForConditionalGeneration,
        )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.device == "cuda":
            self.dtype = torch.bfloat16
            self.model = InstructBlipForConditionalGeneration.from_pretrained(
                self.model_name,
                device_map="auto",
                load_in_8bit=True,
                torch_dtype=self.dtype,
            )
        else:
            self.model = InstructBlipForConditionalGeneration.from_pretrained(
                self.model_name
            )
            self.dtype = torch.float32

        self.processor = InstructBlipProcessor.from_pretrained(self.model_name)
        # self.model.to(self.device)

    def generate(
        self,
        image_embeds,
        qformer_input_ids,
        qformer_attention_mask,
        input_ids,
        attention_mask,
        **generate_kwargs,
    ):
        import torch

        with torch.no_grad(), torch.cuda.amp.autocast():
            if hasattr(self.model, "hf_device_map"):
                # preprocess for `accelerate`
                self.model._preprocess_accelerate()

            batch_size = image_embeds.shape[0]
            # image_embeds = self.model.vision_model(pixel_values, return_dict=True).last_hidden_state

            image_attention_mask = torch.ones(
                image_embeds.size()[:-1], dtype=torch.long, device=image_embeds.device
            )

            query_tokens = self.model.query_tokens.expand(image_embeds.shape[0], -1, -1)
            query_attention_mask = torch.ones(
                query_tokens.size()[:-1], dtype=torch.long, device=image_embeds.device
            )
            if qformer_attention_mask is None:
                qformer_attention_mask = torch.ones_like(qformer_input_ids)
            qformer_attention_mask = torch.cat(
                [query_attention_mask, qformer_attention_mask], dim=1
            )
            query_outputs = self.model.qformer(
                input_ids=qformer_input_ids,
                attention_mask=qformer_attention_mask,
                query_embeds=query_tokens,
                encoder_hidden_states=image_embeds,
                encoder_attention_mask=image_attention_mask,
                return_dict=True,
            )
            query_output = query_outputs.last_hidden_state[:, : query_tokens.size(1), :]

            language_model_inputs = self.model.language_projection(query_output)
            language_attention_mask = torch.ones(
                language_model_inputs.size()[:-1],
                dtype=torch.long,
                device=language_model_inputs.device,
            )

            if input_ids is None:
                input_ids = (
                    torch.LongTensor([[self.model.config.text_config.bos_token_id]])
                    .repeat(batch_size, 1)
                    .to(image_embeds.device, dtype=self.dtype)
                )
            if attention_mask is None:
                attention_mask = torch.ones_like(input_ids)
            attention_mask = torch.cat(
                [
                    language_attention_mask,
                    attention_mask.to(language_attention_mask.device, dtype=self.dtype),
                ],
                dim=1,
            )

            # concatenate query embeddings with prompt embeddings
            inputs_embeds = self.model.get_input_embeddings()(input_ids)
            inputs_embeds = torch.cat(
                [
                    language_model_inputs,
                    inputs_embeds.to(language_model_inputs.device, dtype=self.dtype),
                ],
                dim=1,
            )

            outputs = self.model.language_model.generate(
                inputs_embeds=inputs_embeds,
                attention_mask=attention_mask,
                **generate_kwargs,
            )

            # the InstructBLIP authors used inconsistent tokenizer/model files during training,
            # with the tokenizer's bos token being set to </s> which has ID=2,
            # whereas the model's text config has bos token id = 0
            if self.model.config.text_config.architectures[0] == "LLaMAForCausalLM":
                if isinstance(outputs, torch.Tensor):
                    outputs[outputs == 0] = 2
                else:
                    outputs.sequences[outputs.sequences == 0] = 2

            return outputs

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

        device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.model is None:
            self.model_init()

        query_term = parameters["query_term"]
        text_inputs = self.processor(text=query_term, return_tensors="pt").to(
            self.device, dtype=self.dtype
        )
        with (
            inputs["embeddings"] as input_data,
            inputs["shots"] as shots_data,
            data_manager.create_data("AnnotationData") as annotation_data,
        ):
            generated_texts = []

            for i, embedding in enumerate(input_data.embeddings):
                self.update_callbacks(
                    callbacks, progress=i / len(input_data.embeddings)
                )
                torch_embedding = torch.from_numpy(embedding.embedding).to(
                    self.device, dtype=self.dtype
                )
                outputs = self.generate(
                    **text_inputs,
                    image_embeds=torch_embedding,
                    do_sample=False,
                    num_beams=5,
                    max_length=256,
                    min_length=1,
                    top_p=0.9,
                    repetition_penalty=1.5,
                    length_penalty=1.0,
                    temperature=1,
                )
                generated_text = self.processor.batch_decode(
                    outputs, skip_special_tokens=True
                )[0].strip()
                generated_texts.append((embedding.time, generated_text))
                # embedding = self.model(img)
                # embedding = torch.nn.functional.normalize(embedding, dim=-1)
                # embedding = embedding.cpu().detach()

            for shot in shots_data:
                shot_texts = []
                for time, generated_text in generated_texts:
                    if shot.start <= time and time <= shot.end:
                        shot_texts.append(generated_text)

                annotation_data.annotations.append(
                    Annotation(start=shot.start, end=shot.end, labels=shot_texts)
                )  # Maybe store max_mean_class_prob as well?

            self.update_callbacks(callbacks, progress=1.0)
        return {"annotations": annotation_data}


default_config = {
    "data_dir": "/data/",
}


prob_parameters = {"query_term": ""}


img_embd_requires = {
    "embeddings": ImageEmbeddings,
}

img_embd_provides = {
    "annotations": AnnotationData,
}


@AnalyserPluginManager.export("blip_prob")
class BlipProb(
    AnalyserPlugin,
    config=default_config,
    parameters=prob_parameters,
    version="0.1",
    requires=img_embd_requires,
    provides=img_embd_provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        # self.server = InferenceServer.build(inference_config.get("type"), inference_config.get("params", {}))
        # self.
        self.model_name = config.get("model", "Salesforce/instructblip-flan-t5-xl")
        self.model = None

    def model_init(self):
        import torch
        from transformers import (
            InstructBlipProcessor,
            InstructBlipForConditionalGeneration,
        )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = InstructBlipForConditionalGeneration.from_pretrained(
            self.model_name
        )
        self.processor = InstructBlipProcessor.from_pretrained(self.model_name)

    def generate(
        self,
        image_embeds,
        qformer_input_ids,
        qformer_attention_mask,
        input_ids,
        attention_mask,
        **generate_kwargs,
    ):
        import torch

        with torch.no_grad(), torch.cuda.amp.autocast():
            if hasattr(self.model, "hf_device_map"):
                # preprocess for `accelerate`
                self.model._preprocess_accelerate()

            batch_size = image_embeds.shape[0]
            # image_embeds = self.model.vision_model(pixel_values, return_dict=True).last_hidden_state

            image_attention_mask = torch.ones(
                image_embeds.size()[:-1], dtype=torch.long, device=image_embeds.device
            )

            query_tokens = self.model.query_tokens.expand(image_embeds.shape[0], -1, -1)
            query_attention_mask = torch.ones(
                query_tokens.size()[:-1], dtype=torch.long, device=image_embeds.device
            )
            if qformer_attention_mask is None:
                qformer_attention_mask = torch.ones_like(qformer_input_ids)
            qformer_attention_mask = torch.cat(
                [query_attention_mask, qformer_attention_mask], dim=1
            )
            query_outputs = self.model.qformer(
                input_ids=qformer_input_ids,
                attention_mask=qformer_attention_mask,
                query_embeds=query_tokens,
                encoder_hidden_states=image_embeds,
                encoder_attention_mask=image_attention_mask,
                return_dict=True,
            )
            query_output = query_outputs.last_hidden_state[:, : query_tokens.size(1), :]

            language_model_inputs = self.model.language_projection(query_output)
            language_attention_mask = torch.ones(
                language_model_inputs.size()[:-1],
                dtype=torch.long,
                device=language_model_inputs.device,
            )

            if input_ids is None:
                input_ids = (
                    torch.LongTensor([[self.model.config.text_config.bos_token_id]])
                    .repeat(batch_size, 1)
                    .to(image_embeds.device)
                )
            if attention_mask is None:
                attention_mask = torch.ones_like(input_ids)
            attention_mask = torch.cat(
                [
                    language_attention_mask,
                    attention_mask.to(language_attention_mask.device),
                ],
                dim=1,
            )

            # concatenate query embeddings with prompt embeddings
            inputs_embeds = self.model.get_input_embeddings()(input_ids)
            inputs_embeds = torch.cat(
                [language_model_inputs, inputs_embeds.to(language_model_inputs.device)],
                dim=1,
            )

            outputs = self.model.language_model.generate(
                inputs_embeds=inputs_embeds,
                attention_mask=attention_mask,
                **generate_kwargs,
            )

            # the InstructBLIP authors used inconsistent tokenizer/model files during training,
            # with the tokenizer's bos token being set to </s> which has ID=2,
            # whereas the model's text config has bos token id = 0
            if self.model.config.text_config.architectures[0] == "LLaMAForCausalLM":
                if isinstance(outputs, torch.Tensor):
                    outputs[outputs == 0] = 2
                else:
                    outputs.sequences[outputs.sequences == 0] = 2

            return outputs

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

        device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.model is None:
            self.model_init()

        query_term = parameters["query_term"]
        text_inputs = self.processor(text=query_term, return_tensors="pt").to(device)
        with (
            inputs["embeddings"] as input_data,
            data_manager.create_data("AnnotationData") as annotation_data,
        ):
            for i, embedding in enumerate(input_data.embeddings):
                self.update_callbacks(
                    callbacks, progress=i / len(input_data.embeddings)
                )
                torch_embedding = torch.from_numpy(embedding.embedding).to(self.device)
                outputs = self.generate(
                    **text_inputs,
                    image_embeds=torch_embedding,
                    do_sample=False,
                    num_beams=5,
                    max_length=256,
                    min_length=1,
                    top_p=0.9,
                    repetition_penalty=1.5,
                    length_penalty=1.0,
                    temperature=1,
                )
                generated_text = self.processor.batch_decode(
                    outputs, skip_special_tokens=True
                )[0].strip()
                # embedding = self.model(img)
                # embedding = torch.nn.functional.normalize(embedding, dim=-1)
                # embedding = embedding.cpu().detach()
                annotation_data.annotations.append(
                    Annotation(
                        start=embedding.time,
                        end=embedding.time + embedding.delta_time,
                        labels=[generated_text],
                    )
                )  # Maybe store max_mean_class_prob as well?

            self.update_callbacks(callbacks, progress=1.0)
        return {"annotations": annotation_data}
