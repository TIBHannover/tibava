from __future__ import annotations

import re
import json
import logging
import re
import traceback

from typing import Iterator
from dataclasses import dataclass, field
from datetime import datetime


from .utils import generate_id, create_data_path


@dataclass(kw_only=True, frozen=True)
class PluginData:
    id: str = field(default_factory=generate_id)
    version: str = "1.0"
    last_access: datetime = None
    type: str = field(default="PluginData")
    path: str = None
    data_dir: str = None
    ext: str = None

    def __post_init__(self):
        if not self.path:
            if self.data_dir and self.ext:
                object.__setattr__(self, "path", create_data_path(self.data_dir, self.id, self.ext))

    def to_dict(self) -> dict:
        return {"id": self.id}

    def dumps(self):
        return {"id": self.id, "type": self.type, "ext": self.ext}

    def save(self, data_dir: str, save_blob: bool = True) -> bool:
        logging.debug("[PluginData::save]")
        try:
            if not self.save_blob(data_dir):
                return False
            data_path = create_data_path(data_dir, self.id, "json")
            with open(data_path, "w") as f:
                f.write(json.dumps(self.dumps()))
        except Exception as e:
            logging.error(f"[PluginData::save] {e}")
            logging.error(f"[PluginData::save] {traceback.format_exc()}")
            logging.error(f"[PluginData::save] {traceback.print_stack()}")
            return False
        return True

    def save_blob(self, data_dir=None, path=None) -> bool:
        return True

    @classmethod
    def load(cls, data_dir: str, id: str, load_blob: bool = True) -> PluginData:
        logging.debug(f"[PluginData::load] {id}")
        if len(id) != 32:
            return None

        if not re.match(r"^[a-f0-9]{32}$", id):
            return None

        data_path = create_data_path(data_dir, id, "json")

        data = {}
        with open(data_path, "r") as f:
            data = {**json.load(f), "data_dir": data_dir}

        data_args = cls.load_args(data)
        blob_args = dict()
        if load_blob:
            blob_args = cls.load_blob_args(data_args)

        return cls(**data_args, **blob_args)

    @classmethod
    def load_args(cls, data: dict) -> dict:
        return dict(
            id=data.get("id"),
            # last_access=datetime.fromtimestamp(data.get("last_access")),
            type=data.get("type"),
            data_dir=data.get("data_dir"),
        )

    @classmethod
    def load_blob_args(cls, data: dict) -> dict:
        return {}

    @classmethod
    def load_from_stream(cls, data_dir: str, data_id: str, stream: Iterator[bytes]) -> PluginData:
        return cls(data_dir=data_dir, id=data_id)
