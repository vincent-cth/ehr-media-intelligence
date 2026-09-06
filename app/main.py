from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from .config import settings
from .search import SemanticIndex, build_index_from_store
from .seed import bootstrap_demo
from .storage import SQLiteStore


store = SQLiteStore(settings.db_path)
search_index: SemanticIndex | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global search_index
    if settings.demo_mode and not store.list_patients():
        bootstrap_demo(store)
    search_index = build_index_from_store(store)
    yield
    search_index = None


app = FastAPI(
    title="EHR Media Intelligence Platform",
    description="Search synthetic EHR media normalized to FHIR R4. Not for clinical decisions.",
    version="0.2.0",
    lifespan=lifespan,
)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must contain non-whitespace characters")
        return value


ResourceFilter = Literal["DocumentReference", "DiagnosticReport"]


@app.get("/health")
def health() -> dict:
    counts = store.counts()
    backend = "not-ready"
    if search_index is not None:
        backend = "sentence-transformers" if search_index.embedder._model is not None else "hashing-fallback"
    return {"status": "ok", **counts, "search_backend": backend}


@app.post("/search")
def search(
    body: SearchRequest,
    resource_type: Annotated[ResourceFilter | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> dict:
    global search_index
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    if search_index is None:
        search_index = build_index_from_store(store)
    hits = search_index.search(
        body.query,
        top_k=5,
        resource_type=resource_type,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
    )
    return {"query": body.query, "count": len(hits), "results": [hit.model_dump() for hit in hits]}


@app.get("/patients/{patient_id}")
def patient_detail(patient_id: str) -> dict:
    bundle = store.get_bundle(patient_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient = next(
        (item for item in store.list_patients() if item["patient_id"] == patient_id), None
    )
    return {
        "patient": patient,
        "summary": store.latest_summary(patient_id),
        "records": store.patient_records(patient_id),
        "fhir_validation": store.get_bundle_validation(patient_id),
        "fhir_bundle": bundle,
    }


@app.get("/fhir/validation")
def fhir_validation() -> dict:
    results = store.list_bundle_validations()
    return {
        "fhir_version": "R4 (4.0.1)",
        "valid": all(item["valid"] for item in results),
        "bundle_count": len(results),
        "valid_bundle_count": sum(item["valid"] for item in results),
        "results": results,
    }


@app.post("/admin/rebuild-search")
def rebuild_search() -> dict:
    global search_index
    search_index = build_index_from_store(store)
    search_index.persist()
    return {"indexed_records": len(search_index.metadata)}


@app.get("/")
def ui() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")
