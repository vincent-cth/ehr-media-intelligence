from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from .config import settings
from .models import SearchHit
from .storage import SQLiteStore


class Embedder:
    """SentenceTransformer in production; deterministic hashing fallback keeps tests/offline demo runnable."""
    def __init__(self, model_name: str | None = None, dimension: int = 384):
        self.model_name = model_name or settings.embedding_model
        self.dimension = dimension
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self.dimension = int(self._model.get_sentence_embedding_dimension())
        except Exception:
            self._model = None

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._model is not None:
            vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return np.asarray(vectors, dtype="float32")
        vectors = np.zeros((len(texts), self.dimension), dtype="float32")
        for i, text in enumerate(texts):
            tokens = re.findall(r"[a-z0-9]+", text.lower())
            for token in tokens:
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                idx = int.from_bytes(digest[:4], "little") % self.dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vectors[i, idx] += sign
            norm = float(np.linalg.norm(vectors[i]))
            if norm:
                vectors[i] /= norm
        return vectors


class SemanticIndex:
    def __init__(self, embedder: Embedder | None = None):
        self.embedder = embedder or Embedder()
        self.vectors = np.empty((0, self.embedder.dimension), dtype="float32")
        self.metadata: list[dict[str, Any]] = []
        self._faiss = None
        self._index = None
        try:
            import faiss
            self._faiss = faiss
        except Exception:
            self._faiss = None

    def build(self, records: list[dict[str, Any]]) -> None:
        texts = [self._index_text(r) for r in records]
        self.vectors = self.embedder.encode(texts) if texts else np.empty((0, self.embedder.dimension), dtype="float32")
        self.metadata = [dict(r) for r in records]
        if self._faiss is not None:
            self._index = self._faiss.IndexFlatIP(self.embedder.dimension)
            if len(self.vectors):
                self._index.add(self.vectors)

    @staticmethod
    def _index_text(r: dict[str, Any]) -> str:
        return f"{r.get('patient_name','')} {r.get('title','')} {r.get('resource_type','')} {r.get('text','')} {r.get('summary_snippet','')}"

    def persist(self, index_path: Path | None = None, metadata_path: Path | None = None) -> None:
        index_path = index_path or settings.faiss_index_path
        metadata_path = metadata_path or settings.search_metadata_path
        index_path.parent.mkdir(parents=True, exist_ok=True)
        if self._faiss is not None and self._index is not None:
            self._faiss.write_index(self._index, str(index_path))
        else:
            np.save(str(index_path) + ".npy", self.vectors)
        metadata_path.write_text(json.dumps(self.metadata), encoding="utf-8")

    def search(self, query: str, top_k: int = 5, resource_type: str | None = None, date_from: str | None = None, date_to: str | None = None) -> list[SearchHit]:
        if not query.strip() or not self.metadata:
            return []
        q = self.embedder.encode([query])[0]
        if self._index is not None:
            scores, indices = self._index.search(q.reshape(1, -1), min(max(top_k * 8, 20), len(self.metadata)))
            candidates = [(int(i), float(s)) for i, s in zip(indices[0], scores[0]) if i >= 0]
        else:
            scores = self.vectors @ q
            candidates = sorted(enumerate(scores.tolist()), key=lambda x: x[1], reverse=True)

        hits: list[SearchHit] = []
        for idx, score in candidates:
            r = self.metadata[idx]
            if resource_type and resource_type != "all" and r.get("resource_type") != resource_type:
                continue
            rd = r.get("record_date")
            if rd:
                day = rd[:10]
                if date_from and day < date_from:
                    continue
                if date_to and day > date_to:
                    continue
            snippet = re.sub(r"\s+", " ", r.get("text", "")).strip()
            hits.append(SearchHit(patient_id=r["patient_id"], patient_name=r.get("patient_name", "Unknown"), mrn=r["patient_id"],record_id=r["record_id"], record_date=rd, resource_type=r["resource_type"], title=r["title"],score=round(max(-1.0, min(1.0, float(score))), 4), snippet=snippet[:260]))
            if len(hits) >= top_k:
                break
        return hits


def build_index_from_store(store: SQLiteStore, embedder: Embedder | None = None) -> SemanticIndex:
    index = SemanticIndex(embedder=embedder)
    index.build(store.all_records())
    return index
