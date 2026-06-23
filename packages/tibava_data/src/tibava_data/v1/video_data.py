from typing import Iterator
from dataclasses import dataclass, field

from .utils import generate_id, create_data_path
from .manager import DataManager
from .plugin_data import PluginData

from analyser.proto import analyser_pb2


@DataManager.export("VideoData", analyser_pb2.VIDEO_DATA)
@dataclass(kw_only=True, frozen=True)
class VideoData(PluginData):
    path: str = None
    data_dir: str = None
    ext: str = None
    type: str = field(default="VideoData")

    def to_dict(self) -> dict:
        return super().to_dict()

    def dumps(self):
        dump = super().dumps()
        return {**dump, "path": self.path, "ext": self.ext, "type": self.type}

    @classmethod
    def load_args(cls, data: dict):
        data_dict = super().load_args(data)
        return dict(**data_dict, path=data.get("path"), ext=data.get("ext"))

    @classmethod
    def load_blob_args(cls, data: dict) -> dict:
        return {}

    @classmethod
    def load_from_stream(cls, data_dir: str, data_id: str, stream: Iterator[bytes]) -> PluginData:
        firstpkg = next(stream)
        if hasattr(firstpkg, "ext") and len(firstpkg.ext) > 0:
            ext = firstpkg.ext
        else:
            ext = "mp4"

        path = create_data_path(data_dir, data_id, ext)

        with open(path, "wb") as f:
            print(len(firstpkg.data_encoded))
            f.write(firstpkg.data_encoded)
            for x in stream:
                print(len(x.data_encoded))
                f.write(x.data_encoded)

            f.flush()

        return cls(id=data_id, ext=ext, data_dir=data_dir)

    def dump_to_stream(self, chunk_size=1024) -> Iterator[dict]:
        with open(self.path, "rb") as bytestream:
            while True:
                chunk = bytestream.read(chunk_size)
                if not chunk:
                    break
                yield {"type": analyser_pb2.VIDEO_DATA, "data_encoded": chunk, "ext": self.ext}
