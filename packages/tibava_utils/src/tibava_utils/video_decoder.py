import imageio.v3 as iio
import av
import numpy as np


def parse_meta_av(path, **kwargs):
    try:
        fh = av.open(path)
        stream = fh.streams.video[0]
        frame = next(fh.decode(video=0))
        frame = frame.reformat(format="rgb24")
        return {
            "fps": stream.average_rate,
            "width": frame.width,
            "height": frame.height,
            "size": (frame.width, frame.height),
            "duration": float(stream.duration * stream.time_base),
        }

    except:
        return None


def parse_meta_imageio(path, **kwargs):
    try:
        # TODO
        meta = iio.immeta(path, plugin="FFMPEG", **kwargs)
        return {
            "fps": meta.average_rate,
            "width": meta.width,
            "height": meta.height,
            "size": (meta.width, meta.height),
            "duration": float(meta.duration * meta.time_base),
        }

    except:
        return None


class VideoDecoder:
    # TODO: videos with sample aspect ratio (SAR) not equal to 1:1 are loaded with wrong shape
    def __init__(self, path, max_dimension=None, fps=None, ref_id=None, **kwargs):
        """Provides an iterator over the frames of a video.

        Args:
            path (str): Path to the video file.
            max_dimension (Union[List, int], optional): Resize the video by providing either
                - a list of shape [width, height] or
                - an int that depicts the longer side of the frame.
                Defaults to None.
            fps (int, optional): Frames per second. Defaults to None.
        """
        self._path = path
        self._max_dimension = max_dimension
        self._fps = fps
        self._ref_id = ref_id

        self._meta = parse_meta_av(path)

        self._size = self._meta.get("size")

        self._real_fps = self._meta.get("fps")
        self._duration = self._meta.get("duration")

        self._kwargs = kwargs

    def __iter__(self):
        filter_sequence = []

        if self._fps is not None:
            filter_sequence.append(("fps", {"fps": f"{self._fps}", "round": "up"}))

        if self._max_dimension is not None:
            if isinstance(self._max_dimension, (list, tuple)):
                res = self._max_dimension
            else:
                res = max(self._size[1], self._size[0])

                scale = min(self._max_dimension / res, 1)
                res = (round(self._size[0] * scale), round(self._size[1] * scale))
            filter_sequence.append(
                ("scale", {"width": f"{res[0]}", "height": f"{res[1]}"})
            )
        video_reader = iio.imiter(
            self._path,
            plugin="pyav",
            format="rgb24",
            filter_sequence=filter_sequence,
            **self._kwargs,
        )
        fps = self._real_fps if self._fps is None else self._fps
        for i, frame in enumerate(video_reader):
            yield {
                "time": float(i / fps),
                "index": i,
                "frame": frame,
                "ref_id": self._ref_id,
                "delta_time": float(1 / fps),
            }

    def __len__(self):
        return self.duration() * self.fps()

    def fps(self):
        return float(self._real_fps if self._fps is None else self._fps)

    def duration(self):
        return self._duration


class VideoBatcher:
    def __init__(self, video_decoder: VideoDecoder, batch_size=8):
        self.video_decoder = video_decoder
        self.batch_size = batch_size

    def __iter__(self):
        cache = []
        for x in self.video_decoder:
            cache.append(x)

            if len(cache) >= self.batch_size:
                yield {
                    "time": [x["time"] for x in cache],
                    "index": [x["index"] for x in cache],
                    "frame": np.stack([x["frame"] for x in cache]),
                    "ref_id": [x["ref_id"] for x in cache],
                }
                cache = []

        if len(cache) >= self.batch_size:
            yield {
                "time": [x["time"] for x in cache],
                "index": [x["index"] for x in cache],
                "frame": np.stack([x["frame"] for x in cache]),
                "ref_id": [x["ref_id"] for x in cache],
            }

    def fps(self):
        return self.video_decoder._fps

    def duration(self):
        return self.video_decoder._duration
