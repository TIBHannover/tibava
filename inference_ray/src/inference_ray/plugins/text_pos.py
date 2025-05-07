from typing import List, Callable, Dict
from pathlib import Path
import sys

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager  # type: ignore
from data import AnnotationData, Annotation  # type: ignore

from data import DataManager, Data  # type: ignore

import logging

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "save_dir": Path("/models/text_pos"),
}

default_parameters = {"language_code": "de"}

requires = {
    "annotations": AnnotationData,
}

provides = {"annotations": AnnotationData}


@AnalyserPluginManager.export("text_pos")
class PoSTagging(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

        self.nlp_model = None

        self.pos_dict = {
            "ADJ": 0,
            "ADP": 1,
            "ADV": 2,
            "AUX": 3,
            "CONJ": 4,
            "CCONJ": 4,
            "SCONJ": 4,
            "DET": 5,
            "INTJ": 6,
            "NOUN": 7,
            "NUM": 8,
            "PART": 9,
            "PRON": 10,
            "PROPN": 11,
            "VERB": 12,
            "X": 13,
            "PUNCT": 13,
            "SYM": 13,
        }

        self.model_name = self.config.get("model", "pos_model")

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import numpy as np
        import stanza

        def get_models(
            language_code: str,
        ) -> stanza.Pipeline:
            nlp = stanza.Pipeline(
                lang=language_code,
                dir=str(self.config.get("save_dir")),
                processors="tokenize,pos",
                use_gpu=True,
            )
            return nlp

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
                seg_doc = self.nlp_model(segment.labels[0])
                temp_pos = []
                pos_vector = np.zeros(len(self.pos_dict))
                for sent in seg_doc.sentences:
                    for word in sent.words:
                        temp_pos.append(
                            {
                                "text": word.text,
                                "upos": word.upos,
                                "xpos": word.xpos,
                                "start_char": word.start_char,
                                "end_char": word.end_char,
                            }
                        )

                        if word.upos in self.pos_dict:
                            pos_vector[self.pos_dict[word.upos]] += 1
                        else:
                            pos_vector[self.pos_dict["X"]] += 1

                segment_predictions.append(
                    Annotation(
                        start=segment.start,
                        end=segment.end,
                        labels=[
                            {
                                "speaker": speaker_name,
                                "tags": temp_pos,
                                "vector": pos_vector.tolist(),
                            }
                        ],
                    )
                )

            return segment_predictions

        if self.nlp_model == None:
            self.nlp_model = get_models(parameters.get("language_code"))

        with (
            inputs["annotations"] as input_annotations,
            data_manager.create_data("AnnotationData") as output_data,
        ):
            output_data.name = "PoS-Tagging"
            for _, speaker_data in input_annotations:
                with speaker_data as speaker_data:
                    predictions = classify_segments(
                        speaker_data.annotations, speaker_data.name
                    )
                    output_data.annotations.extend(predictions)

            self.update_callbacks(callbacks, progress=1.0)
            return {
                "annotations": output_data,
            }
