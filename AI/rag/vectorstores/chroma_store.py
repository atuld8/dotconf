#/usr/bin/env python3
# rag/vectorstores/chroma_store.py
from chromadb import PersistentClient

class ChromaStore:
    def __init__(self, path: str, collection: str):
        self.client = PersistentClient(path=path)
        self.col = self.client.get_or_create_collection(collection)

    def upsert(self, ids, embeddings, metadatas, documents, batch_size=5000):
        total = len(ids)
        for i in range(0, total, batch_size):
            j = i + batch_size
            batch_ids = ids[i:j]
            batch_emb = embeddings[i:j]
            batch_meta = metadatas[i:j]
            batch_docs = documents[i:j]

            self.col.upsert(
                ids=batch_ids,
                embeddings=batch_emb,
                metadatas=batch_meta,
                documents=batch_docs
            )
            print(f"Upserted {i} → {min(j, total)}")

    def query(self, embedding, k=8, where=None):
        if where is None:
            return self.col.query(query_embeddings=[embedding], n_results=k)
        return self.col.query(query_embeddings=[embedding], n_results=k, where=where)
