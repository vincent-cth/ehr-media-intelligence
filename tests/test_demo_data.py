from app.demo_corpus import build_raw_demo_records, write_demo_corpus
from app.ingestion import clean_records, ingest_files


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
