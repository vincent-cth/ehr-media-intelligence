from __future__ import annotations

from .config import settings
from .demo_corpus import write_demo_corpus
from .fhir_mapper import build_bundles, validate_bundle
from .ingestion import ingest_files
from .search import build_index_from_store
from .storage import SQLiteStore
from .summarizer import summarize_bundle


def bootstrap_demo(store: SQLiteStore | None = None) -> dict[str, int]:
    store = store or SQLiteStore(settings.db_path)
    json_path, csv_path = write_demo_corpus()
    records = ingest_files([json_path, csv_path])
    store.save_records(records)
    bundles = build_bundles(records)
    for patient_id, bundle in bundles.items():
        valid, errors = validate_bundle(bundle)
        store.save_bundle(patient_id, bundle, valid, errors)
        summarize_bundle(patient_id, bundle, store)
    index = build_index_from_store(store)
    index.persist()
    return {"records": len(records), "patients": len(bundles)}
