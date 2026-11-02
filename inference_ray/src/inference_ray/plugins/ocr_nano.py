import logging
import re
from typing import Callable, Dict, Optional

import numpy as np
from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from tibava_data import (
    Annotation,
    AnnotationData,
    BboxData,
    BboxesData,
    Data,
    DataManager,
    ImagesData,
    StringData,
    StringsData,
    VideoData,
)
from tibava_utils import VideoDecoder

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
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
    version="0.2",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        self.model = None

    def clean_ocr_regex(self, raw_text: str) -> str:
        # Remove noisy metadata tags and their inner content completely
        text = re.sub(
            r"<(watermark|page_number|img)>.*?</\1>", "", raw_text, flags=re.DOTALL
        )

        # Strip all other HTML tags (keeps table cell text intact)
        text = re.sub(r"<[^>]+>", " ", text)

        # Normalize horizontal whitespace and filter out empty lines
        return "".join(
            [
                re.sub(r"\s+", " ", line).strip()
                for line in text.splitlines()
                if line.strip()
            ]
        )

    def init_model(self):
        if self.model is None:
            import os
            import warnings

            warnings.filterwarnings(
                "ignore", category=SyntaxWarning, module="torchao.*"
            )
            warnings.filterwarnings("ignore", message=".*is an Enum subclass.*")

            import torch
            from torchao.quantization import (
                Int8DynamicActivationInt8WeightConfig,
                Int8WeightOnlyConfig,
            )
            from transformers import (
                AutoModelForImageTextToText,
                AutoProcessor,
                AutoTokenizer,
                TorchAoConfig,
            )

            self.device = "cuda" if torch.cuda.is_available() else "cpu"

            if self.device == "cpu":
                num_cores = os.cpu_count() or 4
                torch.set_num_threads(num_cores)
                # Full dynamic int8 (activations + weights) for faster CPU compute
                quant_type = Int8DynamicActivationInt8WeightConfig()
            else:
                # Weight-only int8 on GPU
                quant_type = Int8WeightOnlyConfig()

            nano_model_path = "nanonets/Nanonets-OCR-s"

            # Keep the visual encoder in bfloat16 so vision patch embeddings do not lose precision
            quant_config = TorchAoConfig(
                quant_type=quant_type,
                modules_to_not_convert=["visual"],
            )

            self.model = AutoModelForImageTextToText.from_pretrained(
                nano_model_path,
                dtype=torch.bfloat16,
                device_map=self.device,
                quantization_config=quant_config,
                attn_implementation="sdpa",
                low_cpu_mem_usage=True,
            )
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
                        clean_text = self.clean_ocr_regex(result)
                        if clean_text != "":
                            annotations_data.annotations.append(
                                Annotation(
                                    start=frame.get("time"),
                                    end=end_time,
                                    labels=[clean_text],
                                )
                            )

                    num_frames = video_decoder.duration() * video_decoder.fps()

                return {
                    "strings": strings_data,
                    "annotations": annotations_data,
                }
