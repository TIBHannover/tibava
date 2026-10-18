from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from tibava_data import VideoData, ImagesData, AnnotationData, Annotation
from tibava_data import DataManager, Data

from typing import Callable, Optional, Dict, Union

import logging
import numpy as np


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "ollama_url": "http://ollama:11434",
}

parameters = {"query_term": ""}

requires = {
    "input": Union[VideoData, ImagesData],
}

provides = {
    "annotations": AnnotationData,
}


@AnalyserPluginManager.export("vllm_ollama")
class VLLMOllama(
    AnalyserPlugin,
    config=default_config,
    parameters=parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

        self.ollama_client = None

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:

        from ollama import Client
        import base64
        import imageio.v3 as iio

        def encode_image(image: np.ndarray) -> str:
            jpg_bytes = iio.imwrite("<bytes>", image, extension=".jpg", quality=85)
            return base64.b64encode(jpg_bytes).decode("utf-8")

        if self.ollama_client is None:
            self.ollama_client = Client(
                host=self.config.get("ollama_url", "http://ollama:11434")
            )
            self.ollama_client.pull("gemma4")

        query_term = parameters["query_term"]
        with (
            inputs["input"] as input_data,
            data_manager.create_data("AnnotationData") as output_data,
        ):
            with input_data() as input_iterator:
                for i, frame in enumerate(input_iterator):
                    self.update_callbacks(callbacks, progress=i / len(input_iterator))

                    custom_options = {
                        "temperature": 0,
                        "seed": 42,
                        "top_k": 1,
                        "top_p": 0.0,
                        # 'num_ctx': 4096
                    }
                    # custom_options = {}
                    message = {
                        "role": "user",
                        "content": query_term,
                        "images": [encode_image(frame.get("frame"))],
                    }
                    result = self.ollama_client.chat(
                        model="gemma4",
                        messages=[message],
                    )
                    content = result["message"]["content"]
                    output_data.annotations.append(
                        Annotation(
                            start=frame.get("time"),
                            end=frame.get("time") + frame.get("delta_time"),
                            labels=[content],
                        )
                    )

                self.update_callbacks(callbacks, progress=1.0)
        return {"annotations": output_data}
