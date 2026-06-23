import zipfile
import logging
import yaml
from dataclasses import dataclass, field, fields, asdict
from typing import Callable, Optional, Dict

import uuid

from .fs_handler import FSHandler


def generate_id():
    return uuid.uuid4().hex


@dataclass(kw_only=True)
class Data:
    id: str = field(default_factory=generate_id)
    version: str = field(default="1.0")
    type: str = field(default="PluginData")
    name: Optional[str] = None
    ref_id: Optional[str] = None

    def _register_fs_handler(self, fs: FSHandler) -> None:
        self.fs = fs

    def __enter__(self):
        if hasattr(self, "fs") and self.fs:
            self.fs.open(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "fs") and self.fs:
            self.fs.close(self)

    def check_fs(self):
        return hasattr(self, "fs") and self.fs is not None

    def load(self) -> None:
        data = self.load_dict("meta.yml")
        for x in fields(Data):
            setattr(self, x.name, data.get(x.name, x.default))

    def load_dict(self, filename: str) -> Dict:
        assert self.check_fs(), "No filesystem handler installed"

        with self.fs.open_file(filename, "r") as f:
            decoded_data = f.read().decode("utf-8")
            return yaml.safe_load(decoded_data)

    def save(self) -> None:

        data_dict = {}
        for x in fields(Data):
            data_dict[x.name] = getattr(self, x.name)
        self.save_dict("meta.yml", data_dict)

    def save_dict(self, filename: str, data: Dict) -> None:
        assert self.check_fs(), "No filesystem handler installed"
        assert self.fs.mode == "w", "Data packet is open read only"

        with self.fs.open_file(filename, "w") as f:

            f.write(yaml.safe_dump(data).encode())

    def to_dict(self) -> dict:
        data_dict = {}
        for x in fields(Data):
            data_dict[x.name] = getattr(self, x.name)
        return data_dict
