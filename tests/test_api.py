from fastapi.testclient import TestClient

import app.main as main
from app.fhir_mapper import build_bundles, validate_bundle
from app.ingestion import clean_records
from app.search import Embedder, SemanticIndex
from app.storage import SQLiteStore


def offline_index(store):
    embedder = Embedder.__new__(Embedder)
    embedder.model_name = "offline"
    embedder.dimension = 128
    embedder._model = None
    index = SemanticIndex(embedder=embedder)
    index._faiss = None
    index._index = None
    index.build(store.all_records())
    return index


def test_health_search_detail_and_validation_endpoints(tmp_path, monkeypatch):
    store = SQLiteStore(tmp_path / "api.db")
    records = clean_records([
        {"id":"r1","patient_name":"Avery Demo","mrn":"123","date":"2026-01-02","type":"lab","title":"CBC","text":"normal blood count"},
    ])
    store.save_records(records)
    bundle = next(iter(build_bundles(records).values()))
    valid, errors = validate_bundle(bundle)
    store.save_bundle("00000123", bundle, valid, errors)
    store.save_summary("00000123", "test", {
        "patient_id":"00000123", "chief_concern":"Not stated", "key_diagnoses":[],
        "recent_media_records":["CBC"], "flagged_anomalies":[], "narrative":"Normal blood count documented.",
        "confidence":"high", "generation_method":"llm", "model":"test-model",
        "disclaimer":"AI-generated summary for information retrieval only; not a clinical decision or diagnosis."
    })
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "build_index_from_store", offline_index)

    with TestClient(main.app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["records"] == 1
        search = client.post("/search", json={"query":"blood count"})
        assert search.status_code == 200
        assert search.json()["count"] == 1
        assert search.json()["results"][0]["snippet"].startswith("Normal blood")
        detail = client.get("/patients/00000123")
        assert detail.status_code == 200
        assert detail.json()["fhir_validation"]["valid"] is True
        validation = client.get("/fhir/validation")
        assert validation.json()["valid"] is True
        bad_range = client.post(
            "/search?date_from=2026-02-01&date_to=2026-01-01", json={"query":"blood"}
        )
        assert bad_range.status_code == 422
        blank = client.post("/search", json={"query":"   "})
        assert blank.status_code == 422
