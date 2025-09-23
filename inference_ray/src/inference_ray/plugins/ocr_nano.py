from pprint import pprint

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from utils import VideoDecoder

from data import (
    BboxData,
    BboxesData,
    StringData,
    StringsData,
    ImagesData,
    VideoData,
    AnnotationData,
    Annotation,
)
from data import DataManager, Data

from typing import Callable, Optional, Dict

from utils import VideoDecoder

import numpy as np
import time
import logging


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "ocr_onnx",
}

default_parameters = {
    "fps": 1,
    "det_thresh": 0.5,
    "nms_thresh": 0.4,
    "input_size": (640, 640),
}

requires = {
    "images": ImagesData,
}

provides = {
    "strings": StringsData,
    "annotations": AnnotationData,
}


@AnalyserPluginManager.export("nano_ocr_video")
class NanoOCRVideo(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        self.model = None

    def init_model(self):
        if self.model is None:
            from transformers import (
                AutoTokenizer,
                AutoProcessor,
                AutoModelForImageTextToText,
                HqqConfig,
            )
            import torch
            from hqq.utils.patching import prepare_for_inference
            from hqq.core.quantize import HQQLinear, HQQBackend

            # HQQLinear.set_backend(HQQBackend.PYTORCH_COMPILE)  # Compiled Pytorch

            quant_config = HqqConfig(nbits=4, group_size=64)

            nano_model_path = "nanonets/Nanonets-OCR-s"

            self.model = AutoModelForImageTextToText.from_pretrained(
                nano_model_path,
                # torch_dtype="auto",
                torch_dtype=torch.bfloat16,
                device_map="cpu",
                quantization_config=quant_config,
                # attn_implementation="flash_attention_2",
            )

            prepare_for_inference(self.model, backend="torchao_int4")
            self.model.eval()

            self.tokenizer = AutoTokenizer.from_pretrained(nano_model_path)
            self.processor = AutoProcessor.from_pretrained(nano_model_path)

    def ocr_page_with_nanonets_s(self, image, max_new_tokens=4096):
        prompt = """Extract the text from the above image as if you were reading it naturally. Return the tables in html format. Return the equations in LaTeX representation. If there is an image in the document and image caption is not present, add a small description of the image inside the <img></img> tag; otherwise, add the image caption inside <img></img>. Watermarks should be wrapped in brackets. Ex: <watermark>OFFICIAL COPY</watermark>. Page numbers should be wrapped in brackets. Ex: <page_number>14</page_number> or <page_number>9/22</page_number>. Prefer using ☐ and ☑ for check boxes."""

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    # {"type": "image", "image": f"file://{image_path}"},
                    {"type": "text", "text": prompt},
                ],
            },
        ]
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(
            text=[text], images=[image], padding=True, return_tensors="pt"
        )
        inputs = inputs.to(self.model.device)

        output_ids = self.model.generate(
            **inputs, max_new_tokens=max_new_tokens, do_sample=False
        )
        generated_ids = [
            output_ids[len(input_ids) :]
            for input_ids, output_ids in zip(inputs.input_ids, output_ids)
        ]

        output_text = self.processor.batch_decode(
            generated_ids, skip_special_tokens=True, clean_up_tokenization_spaces=True
        )
        return output_text[0]

    def postprocessing(self, result):
        import re

        p = re.compile(r"<img>.*</img>")
        result = p.sub("", result)

        p = re.compile(r"<watermark>.*</watermark>")
        result = p.sub("", result)

        return result

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:

        self.init_model()

        with inputs["video"] as input_data:
            with input_data.open_video() as f_video:
                video_decoder = VideoDecoder(
                    f_video,
                    fps=parameters.get("fps"),
                    extension=f".{input_data.ext}",
                    ref_id=input_data.id,
                )

                with (
                    data_manager.create_data("StringsData") as strings_data,
                    data_manager.create_data("AnnotationData") as annotations_data,
                ):
                    for frame in video_decoder:
                        result = self.ocr_page_with_nanonets_s(
                            frame["frame"], max_new_tokens=500
                        )
                        logging.warning(f"Raw: {result}")
                        result = self.postprocessing(result)
                        logging.warning(f"Result: {result}")

                        text = StringData()
                        text.text = result
                        strings_data.strings.append(text)

                        end_time = frame.get("time") + 1 / parameters.get("fps")
                        annotations_data.annotations.append(
                            Annotation(
                                start=frame.get("time"),
                                end=end_time,
                                labels=[result],
                            )
                        )

                    num_frames = video_decoder.duration() * video_decoder.fps()

                return {
                    "strings": strings_data,
                    "annotations": annotations_data,
                }
