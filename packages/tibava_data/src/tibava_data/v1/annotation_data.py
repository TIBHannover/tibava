import logging
from typing import Iterator, List
from dataclasses import dataclass, field

import msgpack

from .utils import create_data_path
from .manager import DataManager
from .plugin_data import PluginData

from analyser.proto import analyser_pb2


@dataclass(kw_only=True, frozen=True)
class Annotation:
    start: float
    end: float
    labels: list

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "labels": self.labels}


@DataManager.export("AnnotationData", analyser_pb2.ANNOTATION_DATA)
@dataclass(kw_only=True, frozen=True)
class AnnotationData(PluginData):
    type: str = field(default="AnnotationData")
    ext: str = field(default="msg")
    annotations: List[Annotation] = field(default_factory=list)

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {**meta, "annotations": [ann.to_dict() for ann in self.annotations]}

    def save_blob(self, data_dir=None, path=None):
        logging.debug(f"[AnnotationData::save_blob]")
        try:
            with open(create_data_path(data_dir, self.id, "msg"), "wb") as f:
                # TODO use dump
                f.write(
                    msgpack.packb(
                        {
                            "annotations": [
                                {"start": x.start, "end": x.end, "labels": x.labels} for x in self.annotations
                            ]
                        }
                    )
                )
        except Exception as e:
            logging.error(f"AnnotationData::save_blob {e}")
            return False
        return True

    @classmethod
    def load_blob_args(cls, data: dict) -> dict:
        logging.debug(f"[AnnotationData::load_blob_args]")
        with open(create_data_path(data.get("data_dir"), data.get("id"), "msg"), "rb") as f:
            data = msgpack.unpackb(f.read())
            data = {
                "annotations": [
                    Annotation(start=x["start"], end=x["end"], labels=x["labels"]) for x in data["annotations"]
                ]
            }
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
                yield {"type": analyser_pb2.ANNOTATION_DATA, "data_encoded": chunk, "ext": self.ext}
