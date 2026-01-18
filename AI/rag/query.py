#/usr/bin/env python3
import sys, yaml
from ollama_client import OllamaClient

def fmt_context(hits, max_chars=5000):
    parts = []
    for i, h in enumerate(hits):
        # Chroma style:
        if isinstance(h, dict) and "documents" in h:
            # we queried one vector -> return is batched lists
            for j in range(len(h["documents"][0])):
                doc = h["documents"][0][j]
                meta = h["metadatas"][0][j]
                parts.append(f"[{meta['path']}:{meta['start']}-{meta['end']}]\n{doc}")
        else:
            # SQLite example: row tuple
            _, path, _, start, end, text = h
            parts.append(f"[{path}:{start}-{end}]\n{text}")
    ctx = "\n\n---\n\n".join(parts)
    return ctx[:max_chars]

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Where is the HTTP server initialized?"
    cfg = yaml.safe_load(open("config.yaml"))
    ollama = OllamaClient(cfg["ollama"]["host"])

    # choose vectorstore used at ingest
    if cfg["vectorstore"]["type"] == "chroma":
        from vectorstores.chroma_store import ChromaStore
        store = ChromaStore(cfg["vectorstore"]["path"], cfg["vectorstore"]["collection"])
        # embed the query
        qemb = ollama.embed(cfg["embeddings"]["model"], q)
        res = store.query(qemb, k=8)
        hits = [{
            "documents": [res["documents"][0]],
            "metadatas": [res["metadatas"][0]],
        }]
    else:
        from vectorstores.sqlite_vss_store import SqliteVssStore
        store = SqliteVssStore(cfg["vectorstore"]["path"], dim=768)
        qemb = ollama.embed(cfg["embeddings"]["model"], q)
        hits = store.query(qemb, k=8)

    context = fmt_context(hits)
    prompt = f"You are a senior engineer. Use the code context to answer.\n\nQUESTION:\n{q}\n\nCONTEXT:\n{context}\n\nAnswer with file paths and brief reasoning."
    # Generate with a local LLM
    import requests, json
    r = requests.post(f"{cfg['ollama']['host']}/api/generate",
                      json={"model": "llama3:8b", "prompt": prompt, "stream": False})
    r.raise_for_status()
    print(r.json()["response"])
