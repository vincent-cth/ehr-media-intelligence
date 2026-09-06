from __future__ import annotations

import json
from typing import Any

from .config import settings
from .demo_corpus import write_demo_corpus
from .fhir_mapper import build_bundles, validation_report
from .ingestion import ingest_files, load_csv, load_json
from .search import build_index_from_store
from .storage import SQLiteStore
from .summarizer import summarize_bundle


def bootstrap_demo(store: SQLiteStore | None = None) -> dict[str, Any]:
    store = store or SQLiteStore(settings.db_path)
    json_path, csv_path = write_demo_corpus(settings.demo_data_dir)
    raw_count = len(load_json(json_path)) + len(load_csv(csv_path))
    records = ingest_files([json_path, csv_path])
    store.replace_records(records)

    bundles = build_bundles(records)
    report = validation_report(bundles)
    settings.fhir_validation_report_path.write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    for patient_id, bundle in bundles.items():
        result = report["patients"][patient_id]
        store.save_bundle(patient_id, bundle, result["valid"], result["errors"])

    if not report["valid"]:
        raise RuntimeError(
            f"FHIR validation failed; see {settings.fhir_validation_report_path}"
        )

    for patient_id, bundle in bundles.items():
        summarize_bundle(patient_id, bundle, store)

    index = build_index_from_store(store)
    index.persist()
    return {
        "raw_records": raw_count,
        "records": len(records),
        "duplicates_removed": raw_count - len(records),
        "patients": len(bundles),
        "valid_bundles": report["valid_bundle_count"],
        "indexed_records": len(index.metadata),
    }
