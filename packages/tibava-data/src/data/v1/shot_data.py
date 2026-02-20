import logging
from typing import Iterator, List
from dataclasses import dataclass, field

import msgpack

from .utils import create_data_path
from .manager import DataManager
from .plugin_data import PluginData

from analyser.proto import analyser_pb2


@dataclass(kw_only=True, frozen=True)
class Shot:
    start: float
    end: float

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end}


@DataManager.export("ShotsData", analyser_pb2.SHOTS_DATA)
@dataclass(kw_only=True, frozen=True)
class ShotsData(PluginData):
    type: str = field(default="ShotsData")
    ext: str = field(default="msg")
    shots: List[Shot] = field(default_factory=list)

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {**meta, "shots": [shot.to_dict() for shot in self.shots]}

    def save_blob(self, data_dir=None, path=None):
        logging.debug(f"[ShotsData::save_blob]")
        try:
            with open(create_data_path(data_dir, self.id, "msg"), "wb") as f:
                # TODO use dump
                f.write(msgpack.packb({"shots": [x.to_dict() for x in self.shots]}))
        except Exception as e:
            logging.error(f"ScalarData::save_blob {e}")
            return False
        return True

    @classmethod
    def load_blob_args(cls, data: dict) -> dict:
        logging.debug(f"[ShotsData::load_blob_args]")
        with open(create_data_path(data.get("data_dir"), data.get("id"), "msg"), "rb") as f:
            data = msgpack.unpackb(f.read())
            data = {"shots": [Shot(start=x["start"], end=x["end"]) for x in data["shots"]]}
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
                yield {"type": analyser_pb2.SHOTS_DATA, "data_encoded": chunk, "ext": self.ext}

    def dumps_to_web(self):
        return {"shots": [{"start": x.start, "end": x.end} for x in self.shots]}
