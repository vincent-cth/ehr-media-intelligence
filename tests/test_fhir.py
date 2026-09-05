from app.fhir_mapper import build_bundles
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
