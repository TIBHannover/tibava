import logging
from typing import Callable, Dict

from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager  # type: ignore
from tibava_data import (  # type: ignore  # type: ignore
    Annotation,
    AnnotationData,
    AudioData,
    Data,
    DataManager,
    ListData,
)

default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
}

default_parameters = {"language_code": None}

requires = {
    "audio": AudioData,
}

provides = {
    "transcript": AnnotationData,
    "speaker": AnnotationData,
}


@AnalyserPluginManager.export("whisper_x_origin")
class WhisperXOrigin(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.4",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)
        # inference_config = self.config.get("inference", None)
        # self.server = InferenceServer.build(inference_config.get("type"), inference_config.get("params", {}))

        self.model = None
        self.diarize_model = None
        self.alignment_model = None
        self.model_name = self.config.get("model", "whisper_x")

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import tempfile

        import librosa
        import torch
        import whisperx

        device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.model is None:
            if device == "cuda":
                compute_type = "float16"
            else:
                compute_type = "int8"
            self.model = whisperx.load_model(
                "large-v3",
                device=device,
                compute_type=compute_type,
                language=parameters.get("language_code"),
            )  # TODO originally compute_type="float16" but not supported by m1. probably change back for production
            self.diarize_model = whisperx.diarize.DiarizationPipeline(device=device)
            self.device = device

        with (
            inputs["audio"] as input_data,
            data_manager.create_data("AnnotationData") as transcript_data,
            data_manager.create_data("AnnotationData") as speaker_data,
        ):
            with input_data.open_audio("r") as f_audio:
                temp_file = tempfile.NamedTemporaryFile(suffix=".wav")
                temp_file.write(f_audio.read())

                y = whisperx.load_audio(temp_file.name)
                temp_file.close()
                transcription = self.model.transcribe(
                    audio=y, batch_size=8, language=parameters.get("language_code")
                )

                logging.error("####################")
                logging.error(transcription)
                logging.error("####################")

                # always instantiate new alignment model to match current language
                self.alignment_model, self.metadata = whisperx.load_align_model(
                    language_code=transcription["language"], device=device
                )

                aligned_transcription = whisperx.align(
                    transcription["segments"],
                    self.alignment_model,
                    self.metadata,
                    y,
                    device,
                    return_char_alignments=False,
                )

                diarize_segments = self.diarize_model(y)
                logging.error(diarize_segments)
                logging.error("####################")
                speaker_transcription = whisperx.assign_word_speakers(
                    diarize_segments, aligned_transcription
                )

                transcript = []
                speakers = []
                logging.error(speaker_transcription["segments"])
                logging.error("####################")
                for segment in sorted(
                    speaker_transcription["segments"], key=lambda x: x["start"]
                ):
                    transcript.append(
                        Annotation(
                            start=segment["start"],
                            end=segment["end"],
                            labels=[segment.get("text", "").strip()],
                        )
                    )

                    speakers.append(
                        Annotation(
                            start=segment["start"],
                            end=segment["end"],
                            labels=[segment.get("speaker", "Unknown")],
                        )
                    )

                transcript_data.annotations.extend(transcript)
                transcript_data.name = "Speech Transcript"

                speaker_data.annotations.extend(speakers)
                speaker_data.name = "Speaker"

                self.update_callbacks(callbacks, progress=1.0)
                return {"transcript": transcript_data, "speaker": speaker_data}
