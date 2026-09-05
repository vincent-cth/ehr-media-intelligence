from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path(os.getenv("EHR_DB_PATH", "artifacts/ehr.db"))
    faiss_index_path: Path = Path(os.getenv("FAISS_INDEX_PATH", "artifacts/faiss.index"))
    search_metadata_path: Path = Path(os.getenv("SEARCH_METADATA_PATH", "artifacts/search_metadata.json"))
    summary_cache_path: Path = Path(os.getenv("SUMMARY_CACHE_PATH", "artifacts/summary_cache.json"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL") or None
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes"}

    def ensure_dirs(self) -> None:
        for path in (self.db_path, self.faiss_index_path, self.search_metadata_path, self.summary_cache_path):
            path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
