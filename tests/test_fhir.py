from copy import deepcopy

from app.fhir_mapper import build_bundles, validate_bundle, validation_report
from app.ingestion import clean_records


def test_bundle_contains_required_resources_and_references():
    records = clean_records([
        {"id":"d1","patient_name":"Avery Demo","mrn":"123","dob":"1985-03-14","date":"2026-01-01","title":"Note","text":"hello","encounter_id":"e1"},
        {"id":"r1","patient_name":"Avery Demo","mrn":"123","dob":"1985-03-14","date":"2026-01-02","type":"lab","title":"CBC","text":"normal","encounter_id":"e1"},
    ])
    bundle = next(iter(build_bundles(records).values()))
    types = {e["resource"]["resourceType"] for e in bundle["entry"]}
    assert {"Patient","Encounter","DocumentReference","DiagnosticReport"}.issubset(types)
    ids = {f"{e['resource']['resourceType']}/{e['resource']['id']}" for e in bundle["entry"]}
    for e in bundle["entry"]:
        r=e["resource"]
        if "subject" in r:
            assert r["subject"]["reference"] in ids
    valid, errors = validate_bundle(bundle)
    assert valid, errors


def test_broken_fhir_reference_is_reported_clearly():
    records = clean_records([
        {"id":"r1","patient_name":"Avery Demo","mrn":"123","dob":"1985-03-14","date":"2026-01-02","type":"lab","title":"CBC","text":"normal"},
    ])
    bundle = next(iter(build_bundles(records).values()))
    broken = deepcopy(bundle)
    report = next(
        entry["resource"] for entry in broken["entry"]
        if entry["resource"]["resourceType"] == "DiagnosticReport"
    )
    report["subject"]["reference"] = "Patient/missing"
    valid, errors = validate_bundle(broken)
    assert not valid
    assert any("Broken subject reference: Patient/missing" in error for error in errors)


def test_validation_report_counts_valid_bundles():
    records = clean_records([
        {"id":"d1","patient_name":"Avery Demo","mrn":"123","date":"2026-01-01","title":"Note","text":"hello"},
        {"id":"d2","patient_name":"Jordan Sample","mrn":"456","date":"2026-01-02","title":"Note","text":"hello"},
    ])
    report = validation_report(build_bundles(records))
    assert report["fhir_version"] == "R4 (4.0.1)"
    assert report["valid"] is True
    assert report["bundle_count"] == report["valid_bundle_count"] == 2
