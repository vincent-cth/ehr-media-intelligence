from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import settings
from .search import SemanticIndex, build_index_from_store
from .seed import bootstrap_demo
from .storage import SQLiteStore

app = FastAPI(title="EHR Media Intelligence Platform", version="0.1.0")
store = SQLiteStore(settings.db_path)
search_index: SemanticIndex | None = None

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)

@app.on_event("startup")
def startup() -> None:
    global search_index
    if settings.demo_mode and not store.list_patients():
        bootstrap_demo(store)
    search_index = build_index_from_store(store)

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "patients": len(store.list_patients()), "records": len(store.all_records())}

@app.post("/search")
def search(body: SearchRequest,resource_type: Annotated[str | None, Query()] = None,date_from: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,date_to: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None) -> dict:
    global search_index
    if search_index is None:
        search_index = build_index_from_store(store)
    hits = search_index.search(body.query, top_k=5, resource_type=resource_type, date_from=date_from, date_to=date_to)
    return {"query": body.query, "count": len(hits), "results": [h.model_dump() for h in hits]}

@app.get("/patients/{patient_id}")
def patient_detail(patient_id: str) -> dict:
    bundle = store.get_bundle(patient_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient = next((p for p in store.list_patients() if p["patient_id"] == patient_id), None)
    return {"patient": patient,"summary": store.latest_summary(patient_id),"records": store.patient_records(patient_id),"fhir_bundle": bundle}

@app.post("/admin/rebuild-search")
def rebuild_search() -> dict:
    global search_index
    search_index = build_index_from_store(store)
    search_index.persist()
    return {"indexed_records": len(search_index.metadata)}

@app.get("/")
def ui() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")
