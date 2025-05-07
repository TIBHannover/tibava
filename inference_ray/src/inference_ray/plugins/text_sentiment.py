from typing import List, Callable, Dict
from pathlib import Path

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager  # type: ignore
from data import AnnotationData, Annotation  # type: ignore

from data import DataManager, Data  # type: ignore

import logging

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "save_dir": Path("/models/text_sentiment"),
}

default_parameters = {"model_type": "multilingual"}

requires = {
    "annotations": AnnotationData,
}

provides = {"annotations": AnnotationData}


@AnalyserPluginManager.export("text_sentiment")
class TextSentiment(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

        self.sentiment_model = None
        self.model_type = None

        self.sentiment_dict = {"positive": 0, "negative": 1, "neutral": 2}

        self.model_name = self.config.get("model", "text_sentiment_model")

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import numpy as np
        import torch
        import germansentiment
        import transformers

        device = "cuda:0" if torch.cuda.is_available() else "cpu"

        def get_models(
            model_type: str,
        ) -> tuple[str, germansentiment.SentimentModel | transformers.Pipeline]:
            # TODO currently no sentence-wise sentiment analysis supported
            if model_type == "german-news":
                sentiment_model = germansentiment.SentimentModel(
                    "mdraw/german-news-sentiment-bert"
                )
            elif model_type == "german-general":
                sentiment_model = germansentiment.SentimentModel()
            elif model_type == "multilingual":
                sentiment_model = transformers.pipeline(
                    model="lxyuan/distilbert-base-multilingual-cased-sentiments-student",
                    top_k=None,
                    device=device,
                )
            else:
                raise NotImplementedError(
                    f"Model of type {model_type} is not supported!"
                )
            return model_type, sentiment_model

        def extract_sentiment(model, text, model_type):
            if model_type in ["german-news", "german-general"]:
                preds, probs = model.predict_sentiment(
                    [text], output_probabilities=True
                )
                return preds[0], [probs[0][0][1], probs[0][1][1], probs[0][2][1]]
            elif model_type == "multilingual":
                result = model(text, truncation=True, max_length=512)[0]
                pred = max(result, key=lambda x: x["score"])["label"]
                sorted_results = sorted(
                    result, key=lambda x: self.sentiment_dict[x["label"]]
                )  # fixed probs order
                probs = [r["score"] for r in sorted_results]
                return pred, probs

        def classify_segments(
            segments: List[Annotation], speaker_name: str | None = None
        ) -> List[Annotation]:
            """
            Takes Speaker Turn Segments and performs PoS-Tagging on them

            Args:
                segments (List[Annotation]): List of segments with text annotations and start and end times
                speaker_name (str): Name of speaker

            Returns:
                List[Annotation]: List of segment predictions
            """
            segment_predictions = []

            for segment in segments:
                sentiment_pred, sentiment_probs = extract_sentiment(
                    self.sentiment_model, segment.labels[0], self.model_type
                )

                segment_predictions.append(
                    Annotation(
                        start=segment.start,
                        end=segment.end,
                        labels=[
                            {
                                "speaker": speaker_name,
                                "sentiment_pred": sentiment_pred,
                                "sentiment_probs": sentiment_probs,
                            }
                        ],
                    )
                )

            return segment_predictions

        if self.sentiment_model == None:
            self.model_type, self.sentiment_model = get_models(
                parameters.get("model_type")
            )

        with (
            inputs["annotations"] as input_annotations,
            data_manager.create_data("AnnotationData") as ann_data,
        ):
            ann_data.name = f"Speech Sentiment: {self.model_type.title()}"
            for _, speaker_data in input_annotations:
                with speaker_data as speaker_data:
                    predictions = classify_segments(
                        speaker_data.annotations, speaker_data.name
                    )
                    ann_data.annotations.extend(predictions)

            self.update_callbacks(callbacks, progress=1.0)
            return {
                "annotations": ann_data,
            }
