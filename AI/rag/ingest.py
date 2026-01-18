#/usr/bin/env python3

import os, hashlib, fnmatch, yaml
from pathlib import Path
from chunkers import sliding_window_chunks, language_hint
from ollama_client import OllamaClient

def iter_files(root: Path, includes, excludes):
    for path in root.rglob("*"):
        if not path.is_file(): continue
        rel = path.relative_to(root)
        if any(fnmatch.fnmatch(str(rel), ex) for ex in excludes): continue
        if any(fnmatch.fnmatch(str(rel), inc) for inc in includes):
            yield path

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

if __name__ == "__main__":
    cfg = yaml.safe_load(open(Path(__file__).parent / "config.yaml"))
    root = Path(__file__).parent / cfg["repo_root"]
    max_chars = cfg["chunk"]["max_chars"]; overlap = cfg["chunk"]["overlap"]
    ollama = OllamaClient(cfg["ollama"]["host"])
    model = cfg["embeddings"]["model"]
    vs_type = cfg["vectorstore"]["type"]

    # choose vector store
    if vs_type == "chroma":
        from vectorstores.chroma_store import ChromaStore
        store = ChromaStore(cfg["vectorstore"]["path"], cfg["vectorstore"]["collection"])
    elif vs_type == "sqlite-vss":
        from vectorstores.sqlite_vss_store import SqliteVssStore
        store = SqliteVssStore(cfg["vectorstore"]["path"], dim=768)  # adjust dim to your model
    else:
        raise SystemExit(f"unknown vectorstore {vs_type}")

    ids, embs, metas, docs = [], [], [], []

    for f in iter_files(root, cfg["include_globs"], cfg["exclude_globs"]):
        text = f.read_text(encoding="utf-8", errors="ignore")
        lang = language_hint(f)
        offset = 0
        for chunk in sliding_window_chunks(text, max_chars, overlap):
            doc_id = sha1(f"{f}:{offset}:{offset+len(chunk)}")
            emb = ollama.embed(model=model, text=chunk)
            ids.append(doc_id); embs.append(emb); docs.append(chunk)
            metas.append({
                "path": str(f.relative_to(root)),
                "lang": lang, "start": offset, "end": offset+len(chunk)
            })
            offset += len(chunk)  # naive offset; ok for sliding window
    if ids:
        store.upsert(ids, embs, metas, docs)
        print(f"Indexed {len(ids)} chunks.")
