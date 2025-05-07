from inference_ray.plugin import AnalyserPlugin, AnalyserPluginManager
from data import AnnotationData, Annotation, AudioData, FacesData, VideoData

from data import DataManager, Data

from utils import VideoDecoder

import logging
from typing import Callable, Dict, List, Any
from pathlib import Path
import math
import sys
import numpy as np


default_config = {
    "data_dir": "/data/",
    "host": "localhost",
    "port": 6379,
    "model_name": "active_speaker_detector",
    "save_dir": Path(
        "/models/asd"
    ),  # clone this repo into it: https://github.com/Junhua-Liao/Light-ASD (cuda() calls might be replaced and map_location=device added for torch.load if no cuda is available)
    "model": "talkset",  # or "ava"
}

default_parameters = {
    "sampling_rate": 16000,
    "crop_scale": 0.4,
    "fps": 25,  # needs to be the same as for face_detector/tracker
}

requires = {
    "video": VideoData,
    "audio": AudioData,
    "face_tracks": FacesData,
}

provides = {  # TODO maybe needs to be adjusted for display
    "speaker_tracks": AnnotationData,
}


@AnalyserPluginManager.export("active_speaker_detection")
class ActiveSpeakerDetection(
    AnalyserPlugin,
    config=default_config,
    parameters=default_parameters,
    version="0.1",
    requires=requires,
    provides=provides,
):
    def __init__(self, config=None, **kwargs):
        super().__init__(config, **kwargs)

    def call(
        self,
        inputs: Dict[str, Data],
        data_manager: DataManager,
        parameters: Dict = None,
        callbacks: Callable = None,
    ) -> Dict[str, Data]:
        import torch

        import librosa
        import python_speech_features
        import cv2

        sys.path.append("/models/asd/Light-ASD")
        from ASD import ASD  # type: ignore

        device = "cuda" if torch.cuda.is_available() else "cpu"

        model = ASD()
        model_path = (
            "Light-ASD/weight/finetuning_TalkSet.model"
            if default_config["model"] == "talkset"
            else "Light-ASD/weight/pretrain_AVA_CVPR.model"
        )
        model.loadParameters(default_config["save_dir"] / model_path)
        model.to(device)
        model.eval()

        with (
            inputs["video"] as video_data,
            inputs["audio"] as audio_data,
            inputs["face_tracks"] as face_tracks,
            data_manager.create_data("AnnotationData") as speaker_tracks,
        ):
            with (
                audio_data.open_audio("r") as audio_file,
                video_data.open_video() as video_file,
            ):
                durationSet = {1, 1, 1, 2, 2, 2, 3, 3, 4, 5, 6}
                # TODO cv2.VideoCapture does not work with zipfile to get only frames for each shot (this is quite memory inefficient)
                fps = int(parameters.get("fps"))
                video_decoder = VideoDecoder(
                    video_file,
                    fps=fps,
                    extension=f".{video_data.ext}",
                    ref_id=video_data.id,
                )
                video_frames = [f["frame"] for f in video_decoder]
                audio_array, _ = librosa.load(
                    audio_file, sr=parameters.get("sampling_rate")
                )

                for track in face_tracks.annotations:
                    track_data = track.labels[0]
                    start_idx = int(
                        track.start / video_decoder.duration() * len(audio_array)
                    )
                    end_idx = int(
                        track.end / video_decoder.duration() * len(audio_array)
                    )
                    audioFeature = python_speech_features.mfcc(
                        audio_array[start_idx:end_idx],
                        parameters.get("sampling_rate"),
                        numcep=13,
                        winlen=0.025,
                        winstep=0.010,
                    )
                    face_video_frames = self.crop_face(
                        video_frames[
                            track_data["frames"][0] : track_data["frames"][-1]
                        ],
                        np.array(track_data["bboxes"]),
                        parameters["crop_scale"],
                    )

                    videoFeature = []
                    for face in face_video_frames:
                        face = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
                        face = cv2.resize(face, (224, 224))
                        face = face[
                            int(112 - (112 / 2)) : int(112 + (112 / 2)),
                            int(112 - (112 / 2)) : int(112 + (112 / 2)),
                        ]
                        videoFeature.append(face)
                    videoFeature = np.array(videoFeature)

                    length = min(
                        (audioFeature.shape[0] - audioFeature.shape[0] % 4) / 100,
                        videoFeature.shape[0],
                    )

                    if audioFeature.size == 0 or videoFeature.size == 0:
                        logging.warning(
                            f"Skipping Track {track_data['track_id']} due to empty audio or video feature"
                        )
                        continue

                    audioFeature = audioFeature[: int(round(length * 100)), :]
                    videoFeature = videoFeature[: int(round(length * fps)), :, :]

                    allScore = []
                    for duration in durationSet:
                        batchSize = int(math.ceil(length / duration))
                        scores = []
                        with torch.no_grad():
                            for i in range(batchSize):
                                inputA = (
                                    torch.FloatTensor(
                                        audioFeature[
                                            i
                                            * duration
                                            * 100 : (i + 1)
                                            * duration
                                            * 100,
                                            :,
                                        ]
                                    )
                                    .unsqueeze(0)
                                    .to(device)
                                )
                                inputV = (
                                    torch.FloatTensor(
                                        videoFeature[
                                            i
                                            * duration
                                            * fps : (i + 1)
                                            * duration
                                            * fps,
                                            :,
                                            :,
                                        ]
                                    )
                                    .unsqueeze(0)
                                    .to(device)
                                )

                                if inputA.size(1) == 0 and inputV.size(1) != 0:
                                    inputA = torch.zeros(
                                        (1, inputV.size(1) * 4, inputA.size(2))
                                    ).to(device)
                                elif inputV.size(1) == 0 and inputA.size(1) != 0:
                                    inputV = torch.zeros(
                                        (1, inputA.size(1) // 4, 112, 112)
                                    ).to(device)
                                elif inputA.size(1) == 0 and inputV.size(1) == 0:
                                    logging.warning(
                                        f"Skipping batch {i} due to both inputs being empty"
                                    )
                                    continue

                                embedA = model.model.forward_audio_frontend(inputA)
                                embedV = model.model.forward_visual_frontend(inputV)

                                max_length = max(embedA.size(1), embedV.size(1))

                                if embedA.size(1) < max_length:
                                    padding = torch.zeros(
                                        embedA.size(0),
                                        max_length - embedA.size(1),
                                        embedA.size(2),
                                    ).to(device)
                                    embedA = torch.cat([embedA, padding], dim=1)

                                if embedV.size(1) < max_length:
                                    padding = torch.zeros(
                                        embedV.size(0),
                                        max_length - embedV.size(1),
                                        embedV.size(2),
                                    ).to(device)
                                    embedV = torch.cat([embedV, padding], dim=1)

                                out = model.model.forward_audio_visual_backend(
                                    embedA, embedV
                                )
                                score = model.lossAV.forward(out, labels=None)
                                scores.extend(score)
                        allScore.append(scores)
                    max_length = max(len(scores) for scores in allScore)
                    padded_scores = [
                        scores + [-5] * (max_length - len(scores))
                        for scores in allScore
                    ]
                    allScore = np.round(
                        (np.mean(np.array(padded_scores), axis=0)), 1
                    ).astype(float)

                    smoothed_scores = []
                    for i in range(len(allScore)):
                        s = allScore[max(i - 2, 0) : min(i + 3, len(allScore))]
                        smoothed_scores.append(float(np.mean(s)))

                    speaking_frames = sum(s >= 0 for s in smoothed_scores)
                    speaking_ratio = speaking_frames / len(smoothed_scores)
                    annotation = Annotation(
                        start=track.start,
                        end=track.end,
                        labels=[
                            {
                                "track_id": track_data["track_id"],
                                "frames": track_data["frames"],
                                "bbox": track_data["bboxes"],
                                "is_speaking": speaking_ratio > 0.6,
                                "speaking_ratio": speaking_ratio,
                                "speaking_frames": speaking_frames,
                                "mean_score": float(np.mean(smoothed_scores)),
                                "original_scores": allScore.tolist(),
                                "smoothed_scores": smoothed_scores,
                            }
                        ],
                    )
                    speaker_tracks.annotations.append(annotation)

                return {
                    "speaker_tracks": speaker_tracks,
                }

    def crop_face(
        self,
        frames: List[np.ndarray],
        bboxes: np.ndarray,
        crop_scale: float,
    ) -> List[np.ndarray]:
        """Crops face from video frames and corresponding bounding boxes
        Important: expects bboxes in x1y1x2y2 format

        Args:
            frames (List[np.ndarray]): Video frames to crop
            bboxes (np.ndarray): bboxes in x1y1x2y2 format
            crop_scale (float): Crop scale
        Returns:
            List[np.ndarray]: Cropped Frames
        """
        from scipy import signal
        import cv2

        frame_width = frames[0].shape[1]
        frame_height = frames[0].shape[0]
        bbox_scaling = np.array([frame_width, frame_height, frame_width, frame_height])
        dets = {"x": [], "y": [], "s": []}
        for det in bboxes:
            det *= bbox_scaling
            dets["s"].append(max((det[3] - det[1]), (det[2] - det[0])) / 2)
            dets["y"].append((det[1] + det[3]) / 2)
            dets["x"].append((det[0] + det[2]) / 2)

        dets["s"] = np.array(signal.medfilt(dets["s"], kernel_size=13))
        dets["x"] = np.array(signal.medfilt(dets["x"], kernel_size=13))
        dets["y"] = np.array(signal.medfilt(dets["y"], kernel_size=13))

        cropped_video_frames = []
        for fidx, frame in enumerate(frames):
            image = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            bs = dets["s"][fidx]
            my = dets["y"][fidx]
            mx = dets["x"][fidx]

            y1 = int(my - bs)
            y2 = int(my + bs * (1 + 2 * crop_scale))
            x1 = int(mx - bs * (1 + crop_scale))
            x2 = int(mx + bs * (1 + crop_scale))

            pad_top = max(0, -y1)
            pad_bottom = max(0, y2 - image.shape[0])
            pad_left = max(0, -x1)
            pad_right = max(0, x2 - image.shape[1])

            if pad_top > 0 or pad_bottom > 0 or pad_left > 0 or pad_right > 0:
                image = cv2.copyMakeBorder(
                    image,
                    pad_top,
                    pad_bottom,
                    pad_left,
                    pad_right,
                    cv2.BORDER_CONSTANT,
                    value=[110, 110, 110],
                )

            crop_y1 = max(0, y1 + pad_top)
            crop_y2 = min(image.shape[0], y2 + pad_top)
            crop_x1 = max(0, x1 + pad_left)
            crop_x2 = min(image.shape[1], x2 + pad_left)

            face = image[crop_y1:crop_y2, crop_x1:crop_x2]
            face_resized = cv2.resize(face, (224, 224))
            cropped_video_frames.append(face_resized)

        return cropped_video_frames
