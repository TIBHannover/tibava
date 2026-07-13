import uuid
import logging
from typing import List, Dict

from qdrant_client import QdrantClient
from qdrant_client.http import models

import numpy as np

from analyser.plugins import IndexerPlugin, IndexerFactory
from analyser.utils import get_element

default_config = {
    "index_type": "cos",
    "host": "localhost",
    "port": 6333,
    "grpc": {"port": 50151, "host": "localhost"},
}

default_version = 0.1


@IndexerFactory.export("QDrantIndexer")
class QDrantIndexer(IndexerPlugin):
    def __init__(self, **kwargs):
        super(QDrantIndexer, self).__init__(**kwargs)

        self.port = get_element(self.config, "port")
        if self.port is None:
            self.port = 50151

        self.host = get_element(self.config, "host")
        if self.host is None:
            self.host = "localhost"
        # Read configs
        logging.info(f"[QDrantIndexer] Connection opened")
        self.client = QdrantClient(
            host="qdrant", port=6333, timeout=120, grpc_port=6334, prefer_grpc=False
        )

    def get_collection_indexes(self, name: str = None):
        logging.info(f"[QDrantIndexer]: get_collection_indexes")

        if name is None:
            name = "default"
        results = []
        try:
            collection_info = self.client.get_collection(name)
        except Exception as e:
            logging.error(e)
            return None

        for k, v in collection_info.config.params.vectors.items():
            results.append({"name": k, "size": v.size})

        return results

    def create_collection(self, name, indexes: List[Dict]) -> bool:
        logging.info(f"[QDrantIndexer::create_collection] call")

        # TODO add lock here

        result = self.client.create_collection(
            collection_name=name,
            vectors_config={
                x["name"]: models.VectorParams(
                    size=x["size"],
                    distance=models.Distance.COSINE,
                    multivector_config=models.MultiVectorConfig(
                        comparator=models.MultiVectorComparator.MAX_SIM
                    ),
                )
                for x in indexes
            },
            quantization_config=models.ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(
                    type=models.ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                ),
            ),
        )
        if not result:
            logging.error("[QDrantIndexer::create_collection] error")

    def delete_collection(self, collection_name):
        # TODO add lock here
        logging.info(f"[QDrantIndexer]: delete_collection")

        return self.client.delete_collection(collection_name=collection_name)

    def add_points(self, collection_name, points: List[Dict]):
        # TODO add lock here
        logging.info(f"[QDrantIndexer]: add_points")
        # for k, v in points[0].get("features", {}).items():
        #     logging.error(f"{k}, {len(v)}, {v}")
        logging.info(f"X: {[x.get('meta', {}) for x in points]}")
        result = self.client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=x.get("id", uuid.uuid4().hex),
                    payload=x.get("meta", {}),
                    vector={k: v for k, v in x.get("features", {}).items()},
                )
                for x in points
            ],
        )

    def search(self, queries, filters, size=100):
        results = []

        must = [
            models.FieldCondition(
                key=f'"{f["field"]}"', match=models.MatchValue(value=f["query"])
            )
            for f in filters
            if f["flag"] == "MUST"
        ]
        if len(must) == 0:
            must = None
        should = [
            models.FieldCondition(
                key=f'"{f["field"]}"', match=models.MatchValue(value=f["query"])
            )
            for f in filters
            if f["flag"] == "SHOULD"
        ]
        if len(should) == 0:
            should = None
        must_not = [
            models.FieldCondition(
                key=f'"{f["field"]}"', match=models.MatchValue(value=f["query"])
            )
            for f in filters
            if f["flag"] == "NOT"
        ]
        if len(must_not) == 0:
            must_not = None

        if len(queries) == 0:
            result = self.client.scroll(
                collection_name="default",
                scroll_filter=models.Filter(
                    must=must, should=should, must_not=must_not
                ),
                limit=size,
                with_payload=True,
                with_vectors=True,
            )

            count = 0
            for x in result[0]:
                results.append(
                    {
                        "id": uuid.UUID(x.id).hex,
                        "meta": x.payload,
                        "score": 1,
                        "features": [],
                    }
                )
                count += 1

        for i, q in enumerate(queries):
            result = self.client.search(
                collection_name="default",
                query_vector=models.NamedVector(
                    name=q["index_name"], vector=q["value"]
                ),
                query_filter=models.Filter(must=must, should=should, must_not=must_not),
                limit=size,
                with_payload=True,
                with_vectors=True,
            )
            count = 0
            for x in result:
                results.append(
                    {
                        "id": uuid.UUID(x.id).hex,
                        "meta": x.payload,
                        "score": x.score * q.get("weight", 1.0),
                        "features": [],
                    }
                )
                count += 1

        results = sorted(results, key=lambda x: -x["score"])

        return results
