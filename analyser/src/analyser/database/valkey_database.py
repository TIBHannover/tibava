import os
from tibava_interface.collection_pb2 import CollectionItem
from tibava_interface.data_pb2 import Data as ProtoData
import valkey
import uuid
import msgpack
from tibava_data import DataManager, Data
from tibava_interface.data_pb2 import Data as ProtoData

from typing import Tuple, List, Union


class CollectionRegister:
    pass


class ValkeyCollectionRegister(CollectionRegister):
    def __init__(self):
        self.db = valkey.from_url("valkey://valkey:6379")

    def load(self, point_id: str) -> dict:
        point = self.db.get(point_id)

        if point:
            point = msgpack.unpackb(point)
        else:
            point = {"id": point_id, "data": {}, "version": 1}

        return point

    def add_point(self, point_id: str) -> bool:
        point = self.db.get(point_id)

        if point:
            print(f"ValkeyCollectionRegister {point_id} exists", flush=True)
            point = msgpack.unpackb(point)
        else:
            point = {"id": point_id, "data": {}, "version": 1}

        print(f"ValkeyCollectionRegister {point}", flush=True)

        self.db.set(point_id, msgpack.packb(point))

        return True

    def add_data_to_point(self, point_id: str, data_id: str, name: str) -> bool:
        point = self.db.get(point_id)

        if point:
            point = msgpack.unpackb(point)
        else:
            point = {"id": point_id, "data": {}, "version": 1}

        point["data"][name] = data_id

        self.db.set(point_id, msgpack.packb(point))

        return True


class CollectionDatabase:
    def __init__(
        self, collection_register: CollectionRegister, data_manager: DataManager
    ):
        self.collection_register = collection_register
        self.data_manager = data_manager

    def load_point(self, point_id: str) -> Tuple[Data, List[Data]]:
        point = self.load(point_id=point_id)
        with self.data_manager.load(point["id"]) as data:
            print()

    def add_point(self, data: Data | ProtoData) -> bool:
        return self.collection_register.add_point(data.id)

    def add_data_to_point(
        self, point_id: str, data: Data | ProtoData, name: str = None
    ) -> bool:
        print(point_id, data, name, flush=True)
