#/usr/bin/env python3

import sqlite3
import numpy as np

class SqliteVssStore:
    def __init__(self, db_path: str, dim: int):
        self.conn = sqlite3.connect(db_path)
        self.conn.enable_load_extension(True)
        self.conn.load_extension("vector0")  # sqlite-vss extension must be available
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS docs(
          id TEXT PRIMARY KEY,
          path TEXT, lang TEXT, start INT, end INT, text TEXT
        );
        """)
        self.conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS vss_index
        USING vss0(embedding(#{dim}));
        """.replace("#{dim}", str(dim)))
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS vmap(id TEXT PRIMARY KEY, rowid INTEGER);
        """)
        self.conn.commit()

    def upsert(self, ids, embeddings, metadatas, documents):
        cur = self.conn.cursor()
        for i, emb in enumerate(embeddings):
            meta = metadatas[i]
            cur.execute("INSERT OR REPLACE INTO docs(id,path,lang,start,end,text) VALUES(?,?,?,?,?,?)",
                        (ids[i], meta["path"], meta["lang"], meta["start"], meta["end"], documents[i]))
            vec = np.array(emb, dtype=np.float32).tobytes()
            cur.execute("INSERT INTO vss_index(rowid, embedding) VALUES(NULL, ?)", (vec,))
            rid = cur.lastrowid
            cur.execute("INSERT OR REPLACE INTO vmap(id,rowid) VALUES(?,?)", (ids[i], rid))
        self.conn.commit()

    def query(self, embedding, k=8):
        cur = self.conn.cursor()
        vec = np.array(embedding, dtype=np.float32).tobytes()
        cur.execute("""
        SELECT vmap.id, docs.path, docs.lang, docs.start, docs.end, docs.text
        FROM vss_index
        JOIN vmap ON vmap.rowid = vss_index.rowid
        JOIN docs ON docs.id = vmap.id
        ORDER BY vss_index.distance(embedding, ?) LIMIT ?;
        """, (vec, k))
        return cur.fetchall()
