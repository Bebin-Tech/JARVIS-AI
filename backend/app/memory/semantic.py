"""Local semantic retrieval over approved SQLite records; vectors stay in memory."""

import numpy as np


class SemanticMemory:
    def __init__(self, config, records, client):
        self.config, self.records, self.client = config, records, client

    async def retrieve(self, query):
        memories = self.records.list("memory")
        if not memories:
            return []
        try:
            response = await self.client.post(
                self.config.ollama_url + "/api/embed",
                json={
                    "model": "all-minilm",
                    "input": [query, *[m["content"] for m in memories]],
                    "keep_alive": "1m",
                },
                timeout=30,
            )
            response.raise_for_status()
            vectors = np.asarray(response.json()["embeddings"], dtype=np.float32)
            norms = np.linalg.norm(vectors, axis=1)
            scores = vectors[1:] @ vectors[0] / np.maximum(norms[1:] * norms[0], 1e-9)
            indices = np.argsort(scores)[::-1][:5]
            return [memories[i]["content"] for i in indices if scores[i] > 0.25]
        except Exception:
            words = set(query.lower().split())
            return [
                m["content"] for m in memories if words.intersection(m["content"].lower().split())
            ][:5]
