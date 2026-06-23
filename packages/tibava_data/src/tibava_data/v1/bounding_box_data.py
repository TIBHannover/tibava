import logging
from typing import Iterator, List
from dataclasses import dataclass, field

import msgpack
import msgpack_numpy as m

from .utils import create_data_path
from .manager import DataManager
from .plugin_data import PluginData

from analyser.proto import analyser_pb2


@dataclass(kw_only=True, frozen=True)
class BboxData(PluginData):
    image_id: int = None
    ref_id: str = None
    time: float = None
    delta_time: float = field(default=None)
    x: int = None
    y: int = None
    w: int = None
    h: int = None
    det_score: float = 1.0

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {
            **meta,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "det_score": self.det_score,
            "time": self.time,
            "delta_time": self.delta_time,
            "ref_id": self.ref_id,
            "image_id": self.image_id,
        }


@DataManager.export("BboxesData", analyser_pb2.BBOXES_DATA)
@dataclass(kw_only=True, frozen=True)
class BboxesData(PluginData):
    type: str = field(default="BboxesData")
    ext: str = field(default="msg")
    bboxes: List[BboxData] = field(default_factory=list)

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {**meta, "bboxes": [box.to_dict() for box in self.bboxes]}

    def save_blob(self, data_dir=None, path=None):
        logging.debug(f"[BboxesData::save_blob]")
        try:
            with open(create_data_path(data_dir, self.id, "msg"), "wb") as f:
                f.write(
                    msgpack.packb(
                        {"bboxes": [bbox.to_dict() for bbox in self.bboxes]},
                        default=m.encode,
                    )
                )
        except Exception as e:
            logging.error(f"BboxesData::save_blob {e}")
            return False
        return True

    @classmethod
    def load_blob_args(cls, data: dict) -> dict:
        logging.debug(f"[BboxesData::load_blob_args]")
        with open(create_data_path(data.get("data_dir"), data.get("id"), "msg"), "rb") as f:
            data = msgpack.unpackb(f.read(), object_hook=m.decode)
            # TODO check for det_score
            bboxes = {"bboxes": [BboxData(**bbox) for bbox in data.get("bboxes")]}
        return bboxes

    @classmethod
    def load_from_stream(cls, data_dir: str, data_id: str, stream: Iterator[bytes]) -> PluginData:
        firstpkg = next(stream)
        if hasattr(firstpkg, "ext") and len(firstpkg.ext) > 0:
            ext = firstpkg.ext
        else:
            ext = "msg"

        path = create_data_path(data_dir, data_id, ext)

        with open(path, "wb") as f:
            f.write(firstpkg.data_encoded)
            for x in stream:
                f.write(x.data_encoded)

        data_args = {"id": data_id, "ext": ext, "data_dir": data_dir}

        return cls(**data_args, **cls.load_blob_args(data_args))

    def dump_to_stream(self, chunk_size=1024) -> Iterator[dict]:
        self.save(self.data_dir)
        with open(create_data_path(self.data_dir, self.id, "msg"), "rb") as bytestream:
            while True:
                chunk = bytestream.read(chunk_size)
                if not chunk:
                    break
                yield {"type": analyser_pb2.BBOXES_DATA, "data_encoded": chunk, "ext": self.ext}

    def dumps_to_web(self):
        if hasattr(self.bboxes, "tolist"):
            bboxes = self.bboxes.tolist()  # TODO
        else:
            bboxes = self.bboxes
        return {"bboxes": bboxes}
