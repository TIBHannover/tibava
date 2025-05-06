from typing import Iterator
from dataclasses import dataclass, field


from .utils import create_data_path
from .manager import DataManager
from .plugin_data import PluginData

from analyser.proto import analyser_pb2


@DataManager.export("AudioData", analyser_pb2.AUDIO_DATA)
@dataclass(kw_only=True, frozen=True)
class AudioData(PluginData):
    type: str = field(default="AudioData")

    def dumps(self):
        data_dict = super().dumps()
        return {**data_dict, "path": self.path, "ext": self.ext, "type": self.type}

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
            ext = "mp3"

        path = create_data_path(data_dir, data_id, ext)

        with open(path, "wb") as f:
            f.write(firstpkg.data_encoded)
            for x in stream:
                f.write(x.data_encoded)

            f.flush()

        return cls(id=data_id, ext=ext, data_dir=data_dir)

    def dump_to_stream(self, chunk_size=1024) -> Iterator[dict]:
        with open(self.path, "rb") as bytestream:
            while True:
                chunk = bytestream.read(chunk_size)
                if not chunk:
                    break
                yield {"type": analyser_pb2.AUDIO_DATA, "data_encoded": chunk, "ext": self.ext}
