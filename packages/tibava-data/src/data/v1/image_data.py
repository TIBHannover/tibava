import logging
from typing import Iterator, List
from dataclasses import dataclass, field

import msgpack

from .utils import generate_id, create_data_path
from .manager import DataManager
from .plugin_data import PluginData

from analyser.proto import analyser_pb2
from analyser.utils import ByteFIFO


@dataclass(kw_only=True, frozen=True)
class ImageData(PluginData):
    ref_id: str = None
    time: float = None
    delta_time: float = field(default=None)
    ext: str = field(default="jpg")

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {**meta, "ref_id": self.ref_id, "time": self.time, "delta_time": self.delta_time, "ext": self.ext}


@DataManager.export("ImagesData", analyser_pb2.IMAGES_DATA)
@dataclass(kw_only=True, frozen=True)
class ImagesData(PluginData):
    images: List[ImageData] = field(default_factory=list)
    ext: str = field(default="msg")
    type: str = field(default="ImagesData")

    def to_dict(self) -> dict:
        meta = super().to_dict()
        return {**meta, "images": [image.to_dict() for image in self.images]}

    def save_blob(self, data_dir=None, path=None):
        logging.debug(f"[ImagesData::save_blob]")
        try:
            with open(create_data_path(data_dir, self.id, "msg"), "wb") as f:
                # TODO use dump
                f.write(msgpack.packb({"images": [image.to_dict() for image in self.images]}))
        except Exception as e:
            logging.error(f"ImagesData::save_blob {e}")
            return False
        return True

    @classmethod
    def load_blob_args(cls, data: dict) -> dict:
        logging.debug(f"[ImagesData::load_blob_args]")
        with open(create_data_path(data.get("data_dir"), data.get("id"), "msg"), "rb") as f:
            packdata = msgpack.unpackb(f.read())

            dictdata = {
                "images": [
                    ImageData(
                        time=x["time"],
                        delta_time=x["delta_time"],
                        id=x["id"],
                        ref_id=x.get("ref_id", None),
                        ext=x["ext"],
                        data_dir=data.get("data_dir"),
                    )
                    for x in packdata["images"]
                ]
            }
        return dictdata

    @classmethod
    def load_from_stream(cls, data_dir: str, data_id: str, stream: Iterator[bytes]) -> PluginData:
        firstpkg = next(stream)
        if hasattr(firstpkg, "ext") and len(firstpkg.ext) > 0:
            ext = firstpkg.ext
        else:
            ext = "msg"

        unpacker = msgpack.Unpacker()
        unpacker.feed(firstpkg.data_encoded)
        images = []
        for x in stream:
            unpacker.feed(x.data_encoded)
            for image in unpacker:
                if not isinstance(image, dict):
                    logging.error(f"[ImagesData::load_from_stream] data_encoded should be a dict {image}")
                    return None
                image_id = generate_id()
                image_path = create_data_path(data_dir, image_id, image.get("ext"))
                with open(image_path, "wb") as f:
                    f.write(image.get("image"))
                    f.flush()
                images.append(
                    ImageData(
                        data_dir=data_dir,
                        id=image_id,
                        ref_id=image.get("ref_id"),
                        ext=image.get("ext"),
                        time=image.get("time"),
                        delta_time=image.get("delta_time"),
                    )
                )

        data = cls(images=images, id=data_id)
        data.save_blob(data_dir=data_dir)
        return data

    def dump_to_stream(self, chunk_size=1024) -> Iterator[dict]:
        self.save(self.data_dir)
        buffer = ByteFIFO()
        for image in self.images:
            with open(create_data_path(self.data_dir, image.id, image.ext), "rb") as f:
                image_raw = f.read()
            dump = msgpack.packb(
                {
                    "time": image.time,
                    "delta_time": image.delta_time,
                    "ext": image.ext,
                    "image": image_raw,
                    "ref_id": image.ref_id,
                }
            )
            buffer.write(dump)

            while len(buffer) > chunk_size:
                chunk = buffer.read(chunk_size)
                # if not chunk:
                #     break

                yield {"type": analyser_pb2.IMAGES_DATA, "data_encoded": chunk, "ext": self.ext}

        chunk = buffer.read(chunk_size)
        if chunk:
            yield {"type": analyser_pb2.IMAGES_DATA, "data_encoded": chunk, "ext": self.ext}

    def dumps_to_web(self):
        return {
            "images": [
                {
                    "time": image.time,
                    "delta_time": image.delta_time,
                    "ext": image.ext,
                    "id": image.id,
                    "ref_id": image.ref_id,
                }
                for image in self.images
            ]
        }
