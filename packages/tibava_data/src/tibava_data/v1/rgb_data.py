import logging
from typing import Iterator, List
from dataclasses import dataclass, field

import msgpack
import msgpack_numpy as m
import numpy.typing as npt
import numpy as np

from .utils import create_data_path
from .manager import DataManager
from .plugin_data import PluginData

from analyser.proto import analyser_pb2


@DataManager.export("RGBData", analyser_pb2.RGB_DATA)
@dataclass(kw_only=True, frozen=True)
class RGBData(PluginData):
    type: str = field(default="RGBData")
    ext: str = field(default="msg")
    colors: npt.NDArray = field(default_factory=np.ndarray)
    time: List[float] = field(default_factory=list)
    delta_time: float = field(default=None)

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {**meta, "colors": self.colors, "time": self.time, "delta_time": self.delta_time}

    def save_blob(self, data_dir=None, path=None):
        logging.debug(f"[RGBData::save_blob]")
        try:
            with open(create_data_path(data_dir, self.id, "msg"), "wb") as f:
                f.write(
                    msgpack.packb(
                        {"colors": self.colors, "time": self.time, "delta_time": self.delta_time}, default=m.encode
                    )
                )
        except Exception as e:
            logging.error(f"RGBData::save_blob {e}")
            return False
        return True

    @classmethod
    def load_blob_args(cls, data: dict) -> dict:
        logging.debug(f"[RGBData::load_blob_args]")
        with open(create_data_path(data.get("data_dir"), data.get("id"), "msg"), "rb") as f:
            data = msgpack.unpackb(f.read(), object_hook=m.decode)
        return data

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

            f.flush()

        data_args = {"id": data_id, "ext": ext, "data_dir": data_dir}

        return cls(**data_args, **cls.load_blob_args(data_args))

    def dump_to_stream(self, chunk_size=1024) -> Iterator[dict]:
        self.save(self.data_dir)
        with open(create_data_path(self.data_dir, self.id, "msg"), "rb") as bytestream:
            while True:
                chunk = bytestream.read(chunk_size)
                if not chunk:
                    break
                yield {"type": analyser_pb2.RGB_DATA, "data_encoded": chunk, "ext": self.ext}

    def dumps_to_web(self):
        if hasattr(self.colors, "tolist"):
            colors = self.colors.tolist()
        else:
            colors = self.colors
        return {"colors": colors, "time": self.time, "delta_time": self.delta_time}
