import logging
from typing import Iterator, List, Union
from dataclasses import dataclass, field

import msgpack
import msgpack_numpy as m

from .utils import create_data_path, generate_id
from .manager import DataManager
from .plugin_data import PluginData

from analyser.proto import analyser_pb2


@DataManager.export("ListData", analyser_pb2.LIST_DATA)
@dataclass(kw_only=True, frozen=True)
class ListData(PluginData):
    type: str = field(default="ListData")
    ext: str = field(default="msg")
    data: List[PluginData] = field(default_factory=list)
    index: List[Union[str, int]] = field(default=None)

    def __post_init__(self):
        if not self.index:
            object.__setattr__(self, "index", list(range(len(self.data))))

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {**meta, "data": [d.to_dict() for d in self.data], "index": self.index}

    def save_blob(self, data_dir=None, path=None):
        logging.debug(f"[ListData::save_blob]")
        try:
            for d in self.data:
                d.save(data_dir)
        except Exception as e:
            logging.error(f"ListData::save_blob {e}")
            return False

        try:
            with open(create_data_path(data_dir, self.id, "msg"), "wb") as f:
                # TODO use dump
                f.write(msgpack.packb({"data": [{"id": d.id} for d in self.data], "index": self.index}))
        except Exception as e:
            logging.error(f"ListData::save_blob {e}")
            return False
        return True

    @classmethod
    def load_blob_args(cls, data: dict) -> dict:
        logging.debug(f"[ListData::load_blob_args]")
        with open(create_data_path(data.get("data_dir"), data.get("id"), "msg"), "rb") as f:
            data_decoded = msgpack.unpackb(f.read(), object_hook=m.decode)

        return {
            "data": [DataManager._load(data.get("data_dir"), d.get("id")) for d in data_decoded.get("data")],
            "index": data_decoded.get("index"),
        }

    @classmethod
    def load_from_stream(cls, data_dir: str, data_id: str, stream: Iterator[bytes]) -> PluginData:
        class DataYielder:
            def __init__(self, stream):
                self.cache = []
                self.stream = stream
                self.empty = False
                self.index = {}

            def push(self, data):
                self.cache.append(data)

            def get_next(self):
                if len(self.cache) > 0:
                    return self.cache.pop()

                return next(stream)

            def __iter__(self):
                try:
                    firstpkg = self.get_next()
                    firstpkg_decoded = msgpack.unpackb(firstpkg.data_encoded)
                    self.index[firstpkg_decoded.get("i")] = firstpkg_decoded.get("id")
                    chunk = firstpkg_decoded.get("chunk")

                    yield analyser_pb2.DownloadDataResponse(**chunk)
                    while True:
                        pkg = self.get_next()
                        pkg_decoded = msgpack.unpackb(pkg.data_encoded)

                        self.index[pkg_decoded.get("i")] = pkg_decoded.get("id")
                        if firstpkg_decoded.get("i") == pkg_decoded.get("i"):
                            chunk = pkg_decoded.get("chunk")

                            yield analyser_pb2.DownloadDataResponse(**chunk)
                        else:
                            self.push(pkg)
                            break
                except StopIteration as e:
                    self.empty = True
                    return

        yielder = DataYielder(stream)

        data = []
        while not yielder.empty:
            d, h = DataManager._load_from_stream(data_dir, yielder, data_id=generate_id())
            data.append(d)

        data_obj = cls(
            id=data_id,
            data_dir=data_dir,
            data=data,
            index=list(map(lambda x: x[1], sorted(yielder.index.items(), key=lambda x: x[0]))),
        )

        data_obj.save(data_dir=data_dir)
        return data_obj

    def dump_to_stream(self, chunk_size=1024) -> Iterator[dict]:
        self.save(self.data_dir)
        for i, (id, d) in enumerate(zip(self.index, self.data)):
            for chunk in d.dump_to_stream(chunk_size=chunk_size):

                yield {
                    "type": analyser_pb2.LIST_DATA,
                    "data_encoded": msgpack.packb({"i": i, "id": id, "chunk": chunk}),
                    "ext": self.ext,
                }

    def dumps_to_web(self):
        return {"y": self.y.tolist(), "time": self.time}
