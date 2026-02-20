import logging
import yaml
from typing import List, Union
from collections.abc import Iterator, Iterable

from dataclasses import dataclass, field, fields
import imageio.v3 as iio

import numpy.typing as npt
import numpy as np

from ..manager import DataManager
from ..data import Data
from interface import analyser_pb2


@dataclass(kw_only=True)
class ImageData(Data):
    type: str = field(default="ImageData")
    time: float = None
    delta_time: float = field(default=None)
    ext: str = field(default="jpg")

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "time": self.time,
            "delta_time": self.delta_time,
            "ext": self.ext,
        }


@DataManager.export("ImagesData", analyser_pb2.IMAGES_DATA)
@dataclass(kw_only=True)
class ImagesData(Data):
    type: str = field(default="ImagesData")
    images: List[ImageData] = field(default_factory=list)

    def load(self) -> None:
        super().load()
        assert self.check_fs(), "No filesystem handler installed"

        data = self.load_dict("images_data.yml")
        self.images = [ImageData(**x) for x in data.get("images")]

    def save(self) -> None:
        super().save()
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        self.save_dict(
            "images_data.yml", {"images": [x.to_dict() for x in self.images]}
        )

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "images": [x.to_dict() for x in self.images],
        }

    def __len__(self) -> int:
        return len(self.images)

    def __iter__(self) -> Iterator:
        yield from self.images

    def __call__(self, **kwargs) -> "ImagesIterator":
        return ImagesIterator(self)

    def save_image(self, image: npt.ArrayLike, **kwargs) -> None:
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"
        image_data = ImageData(**kwargs)
        try:

            encoded = iio.imwrite("<bytes>", image, extension=".jpg")
            with self.fs.open_file(f"{image_data.id}.jpg", "w") as f:
                f.write(encoded)
        except:
            logging.error("[ImagesData] Could not add a new image")
            return None

        self.images.append(image_data)

    def load_image(self, image: Union[ImageData, str]) -> npt.ArrayLike:
        assert self.check_fs(), "No filesystem handler installed"

        image_id = image.id if isinstance(image, ImageData) else image
        image_ext = image.ext if isinstance(image, ImageData) else "jpg"
        try:
            with self.fs.open_file(f"{image_id}.{image_ext}", "r") as f:
                return iio.imread(f.read(), extension=f".{image_ext}")
        except Exception as e:
            logging.error(
                f"[ImagesData] Could not load a image with id {image_id} (Exception: {e})"
            )
            return None

    def extract_all(self, data_manager: DataManager) -> None:

        for image in self:
            logging.debug(f"[ImagesData] Extract {image.id}")
            image_id = image.id if isinstance(image, ImageData) else image
            image_ext = image.ext if isinstance(image, ImageData) else "jpg"
            output_path = data_manager._create_file_path(image_id, image_ext)
            with self.fs.open_file(f"{image_id}.{image_ext}", "r") as f_in:
                with open(output_path, "wb") as f_out:
                    while True:
                        chunk = f_in.read(1024)
                        if not chunk:
                            break
                        f_out.write(chunk)


class ImagesIterator:
    def __init__(self, data: ImagesData):
        self.data = data

    def __enter__(self):
        return self

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        for i, image in enumerate(self.data):
            image_data = self.data.load_image(image)
            yield {
                "time": image.time,
                "index": i,
                "frame": image_data,
                "id": image.id,
                "ref_id": image.ref_id,
                "delta_time": image.delta_time,
            }

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
