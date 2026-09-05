from app.ingestion import clean_records, normalize_mrn, parse_date


def test_inconsistent_date_and_gender_are_normalized():
    row = {"id":"1","patient_name":"ada example","mrn":"12-34","dob":"03/14/1985","gender":"F","date":"03/03/2026","text":"note"}
    record = clean_records([row])[0]
    assert record.patient.dob.isoformat() == "1985-03-14"
    assert record.patient.gender == "female"
    assert record.patient.mrn == "00001234"
    assert any(a.field == "dob" for a in record.audit_log)


def test_missing_mrn_generates_stable_temporary_identifier():
    row = {"id":"2","patient_name":"Morgan Test","dob":"1992-08-22","text":"note"}
    a = clean_records([row])[0]
    b = clean_records([row])[0]
    assert a.patient.mrn.startswith("TEMP")
    assert a.patient.mrn == b.patient.mrn


def test_duplicates_removed_and_conflicting_mrn_resolved():
    rows = [
        {"id":"a","patient_name":"Avery Demo","mrn":"12-34-56","dob":"1985-03-14","date":"2026-01-01","title":"Lab","type":"lab","text":"same"},
        {"id":"b","patient_name":"Avery Demo","mrn":"00123456","dob":"1985-03-14","date":"2026-01-01","title":"Lab","type":"lab","text":"same"},
        {"id":"c","patient_name":"Avery Demo","mrn":"99999999","dob":"1985-03-14","date":"2026-01-02","title":"Note","text":"different"},
    ]
    cleaned = clean_records(rows)
    assert len(cleaned) == 2
    assert cleaned[1].patient.mrn == "00123456"
    assert any("conflicting" in a.action for a in cleaned[1].audit_log)
