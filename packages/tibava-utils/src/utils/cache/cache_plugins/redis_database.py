from typing import Any, List, Iterator
import logging

import valkey
import msgpack

from utils.cache import CacheManager, Cache

default_config = {"db": 0, "host": "valkey", "port": 6379, "tag": "data"}


class Batcher:
    def __init__(self, iterable, n=1):
        self.iterable = iterable
        self.n = n

    def __iter__(self):
        l = len(self.iterable)
        for ndx in range(0, l, self.n):
            yield self.iterable[ndx : min(ndx + self.n, l)]


@CacheManager.export("valkey")
class valkeyCache(Cache, config=default_config, version="0.1"):
    def __init__(self, config=None):
        super().__init__(config)
        self.r = valkey.Valkey(
            host=self.config.get("host"),
            port=self.config.get("port"),
            db=self.config.get("db"),
        )

    def set(self, id: str, data: Any) -> bool:
        try:
            packed = msgpack.packb(data)
            tag = self.config.get("tag")
            self.r.set(f"{tag}:{id}", packed)
        except Exception as e:
            logging.error(f"valkeyCache {e}")

    def delete(self, id: str) -> bool:
        try:
            tag = self.config.get("tag")
            return self.r.delete(f"{tag}:{id}")
        except Exception as e:
            logging.error(f"valkeyCache {e}")
            return None

    def get(self, id: str) -> Any:
        try:
            tag = self.config.get("tag")
            packed = self.r.get(f"{tag}:{id}")
            if packed is None:
                return None
            return msgpack.unpackb(packed)
        except Exception as e:
            logging.error(f"valkeyCache {e}")
            return None

    def keys(self) -> List[str]:
        try:
            tag = self.config.get("tag")
            start = len(f"{tag}:")
            keys = self.r.scan_iter(f"{tag}:*", 500)

            # print([x for x in Batcher(keys, 2)])
            return [key[start:].decode("utf-8") for key in keys]
        except Exception as e:
            logging.error(f"valkeyCache {e}")
            return []

    def __iter__(self) -> Iterator:
        try:
            tag = self.config.get("tag")
            start = len(f"{tag}:")
            keys = list(self.r.scan_iter(f"{tag}:*", 500))
            while len(keys) > 0:
                batch_keys = keys[:500]
                keys = keys[500:]

                values = self.r.mget(batch_keys)
                for k, v in zip(batch_keys, values):
                    yield k[start:].decode("utf-8"), msgpack.unpackb(v)

        except Exception as e:
            logging.error(f"valkeyCache {e}")
            yield from []
