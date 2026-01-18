#/usr/bin/env python3

from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct

class QdrantStore:
    def __init__(self, host: str, port: int, collection: str, dim: int):
        self.q = QdrantClient(host=host, port=port)
        self.collection = collection
        self.q.recreate_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
        )

    def upsert(self, ids, embeddings, metadatas, documents):
        points = []
        for i, emb in enumerate(embeddings):
            p = PointStruct(
                id=ids[i],
                vector=emb,
                payload={**metadatas[i], "text": documents[i]}
            )
            points.append(p)
        self.q.upsert(collection_name=self.collection, points=points)

    def query(self, embedding, k=8, query_filter=None):
        return self.q.search(collection_name=self.collection, query_vector=embedding, limit=k, query_filter=query_filter)
