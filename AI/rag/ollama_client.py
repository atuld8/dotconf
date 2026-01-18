#/usr/bin/env python3
import requests

class OllamaClient:
    def __init__(self, host: str):
        self.host = host.rstrip("/")

    def embed(self, model: str, text: str) -> list[float]:
        r = requests.post(f"{self.host}/api/embeddings",
                          json={"model": model, "prompt": text}, timeout=120)
        r.raise_for_status()
        return r.json()["embedding"]
