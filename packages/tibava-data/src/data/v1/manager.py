from __future__ import annotations

import logging
import json
import tempfile
import hashlib
from typing import Any, Iterator

from .plugin_data import PluginData
from .utils import create_data_path, generate_id


class DataManager:
    _data_name_lut = {}
    _data_enum_lut = {}

    def __init__(self, data_dir=None, database=None):
        self.database = database
        if not data_dir:
            data_dir = tempfile.mkdtemp()
        self.data_dir = data_dir

    @classmethod
    def export(cls, name: str, enum_value: int):
        def export_helper(data):
            cls._data_name_lut[name] = data
            cls._data_enum_lut[enum_value] = data
            return data

        return export_helper

    @classmethod
    def _load_from_stream(cls, data_dir: str, data: Iterator[Any], data_id: str, save_meta=True) -> PluginData:
        logging.debug(f"data.py (load_from_stream): {data}")
        datastream = iter(data)
        firstpkg = next(datastream)

        hash_stream = hashlib.sha1()

        def data_generator():
            yield firstpkg

            hash_stream.update(firstpkg.data_encoded)
            for x in datastream:
                hash_stream.update(x.data_encoded)
                yield x

        data = None
        if firstpkg.type not in cls._data_enum_lut:
            return None
        data = cls._data_enum_lut[firstpkg.type].load_from_stream(
            data_dir=data_dir, data_id=data_id, stream=data_generator()
        )

        if save_meta and data is not None:
            with open(create_data_path(data_dir, data.id, "json"), "w") as f:
                f.write(json.dumps(data.dumps(), indent=2))

        return data, hash_stream.hexdigest()

    def load_from_stream(self, data: Iterator[Any], data_id: str = None, save_meta=True) -> PluginData:
        if not data_id:
            data_id = generate_id()
        return self._load_from_stream(self.data_dir, data, data_id, save_meta)

    def dump_to_stream(self, data: PluginData):
        return data.dump_to_stream()

    def check(self, data_id: str, data_dir: str = None) -> PluginData:
        if not data_dir:
            data_dir = self.data_dir
        try:
            data = PluginData.load(data_dir=data_dir, id=data_id, load_blob=False)
            return data
        except:
            return None

    @classmethod
    def _load(self, data_dir: str, data_id: str) -> PluginData:
        data = PluginData.load(data_dir=data_dir, id=data_id, load_blob=False)
        if data.type not in self._data_name_lut:
            logging.error(f"[DataManager::load] unknow type {data.type}")
            return None

        return self._data_name_lut[data.type].load(data_dir=data_dir, id=data_id)

    def load(self, data_id: str) -> PluginData:
        return self._load(self.data_dir, data_id)

    def save(self, data):
        data.save(self.data_dir, save_blob=True)
