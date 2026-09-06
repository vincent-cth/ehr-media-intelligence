from app.demo_corpus import build_raw_demo_records, write_demo_corpus
from pathlib import Path

from app.ingestion import clean_records, ingest_files, load_csv, load_json


ROOT = Path(__file__).resolve().parents[1]


def test_demo_corpus_has_60_unique_records_and_required_edge_cases(tmp_path):
    json_records, csv_records = build_raw_demo_records()
    raw_records = [*json_records, *csv_records]
    cleaned = clean_records(raw_records)

    assert len(raw_records) == 62
    assert len(cleaned) == 60
    assert len({record.patient.mrn for record in cleaned}) == 20
    actions = [event.action for record in cleaned for event in record.audit_log]
    assert "resolved conflicting patient identifier" in actions
    assert "filled missing identifier from matched patient" in actions
    assert "generated missing identifier" in actions

    paths = write_demo_corpus(tmp_path)
    assert len(ingest_files(paths)) == 60


def test_committed_data_directory_contains_the_full_corpus():
    json_records = load_json(ROOT / "data" / "sample_ehr.json")
    csv_records = load_csv(ROOT / "data" / "sample_notes.csv")
    assert len(json_records) == 41
    assert len(csv_records) == 21
    assert len(clean_records([*json_records, *csv_records])) == 60
