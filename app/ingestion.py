from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from .models import AuditEvent, CleanRecord, PatientDemographics

DATE_FORMATS = (
    "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d", "%d-%b-%Y",
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%m/%d/%Y %H:%M",
)

GENDER_MAP = {
    "m": "male", "male": "male", "man": "male", "1": "male",
    "f": "female", "female": "female", "woman": "female", "2": "female",
    "o": "other", "other": "other", "nonbinary": "other", "non-binary": "other",
    "u": "unknown", "unknown": "unknown", "": "unknown", "none": "unknown",
}


def _first(raw: dict[str, Any], *keys: str, default: Any = None) -> Any:
    lower = {str(k).lower(): v for k, v in raw.items()}
    for key in keys:
        if key.lower() in lower and lower[key.lower()] not in (None, ""):
            return lower[key.lower()]
    return default


def parse_date(value: Any) -> date | None:
    if value in (None, "", "null"):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, "", "null"):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def normalize_mrn(value: Any) -> str | None:
    if value in (None, ""):
        return None
    compact = re.sub(r"[^A-Za-z0-9]", "", str(value)).upper()
    if not compact:
        return None
    if compact.isdigit():
        return compact.zfill(8)
    return compact


def normalize_gender(value: Any) -> str:
    return GENDER_MAP.get(str(value or "").strip().lower(), "unknown")


def normalize_name(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return "Unknown Patient"
    return " ".join(part.capitalize() for part in text.split(" "))


def _temporary_mrn(name: str, dob: date | None) -> str:
    seed = f"{name}|{dob.isoformat() if dob else 'unknown'}".encode()
    return "TEMP" + hashlib.sha1(seed).hexdigest()[:8].upper()


def _resource_type(raw: dict[str, Any]) -> str:
    value = str(_first(raw, "resource_type", "type", "record_type", default="DocumentReference")).strip().lower()
    return "DiagnosticReport" if any(x in value for x in ("lab", "diagnostic", "report", "imaging")) else "DocumentReference"


def clean_record(raw: dict[str, Any], canonical_mrn: str | None = None) -> CleanRecord:
    audit: list[AuditEvent] = []
    source_id = str(_first(raw, "source_id", "id", "record_id", default="")).strip()
    if not source_id:
        source_id = "rec-" + hashlib.sha1(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()[:12]
        audit.append(AuditEvent(field="source_id", action="generated missing identifier", after=source_id, severity="warning"))

    raw_name = _first(raw, "patient_name", "name", "full_name")
    name = normalize_name(raw_name)
    if name != str(raw_name or "").strip():
        audit.append(AuditEvent(field="patient_name", action="normalized", before=str(raw_name or ""), after=name))

    raw_dob = _first(raw, "dob", "date_of_birth", "birth_date")
    dob = parse_date(raw_dob)
    if raw_dob and dob is None:
        audit.append(AuditEvent(field="dob", action="unparseable date retained as missing", before=str(raw_dob), severity="warning"))
    elif raw_dob and str(raw_dob) != dob.isoformat():
        audit.append(AuditEvent(field="dob", action="normalized date", before=str(raw_dob), after=dob.isoformat()))

    raw_gender = _first(raw, "gender", "sex", default="unknown")
    gender = normalize_gender(raw_gender)
    if str(raw_gender).strip().lower() != gender:
        audit.append(AuditEvent(field="gender", action="normalized code", before=str(raw_gender), after=gender))

    raw_mrn = _first(raw, "mrn", "patient_id", "medical_record_number")
    mrn = normalize_mrn(raw_mrn)
    if canonical_mrn and mrn and mrn != canonical_mrn:
        audit.append(AuditEvent(field="mrn", action="resolved conflicting patient identifier", before=mrn, after=canonical_mrn, severity="warning"))
        mrn = canonical_mrn
    elif canonical_mrn and not mrn:
        mrn = canonical_mrn
        audit.append(AuditEvent(field="mrn", action="filled missing identifier from matched patient", after=mrn, severity="warning"))
    if mrn is None:
        mrn = _temporary_mrn(name, dob)
        audit.append(AuditEvent(field="mrn", action="generated temporary identifier", after=mrn, severity="warning"))
    elif raw_mrn and str(raw_mrn) != mrn:
        audit.append(AuditEvent(field="mrn", action="normalized", before=str(raw_mrn), after=mrn))

    raw_dt = _first(raw, "record_date", "date", "timestamp", "created_at")
    record_date = parse_datetime(raw_dt)
    if raw_dt and record_date is None:
        audit.append(AuditEvent(field="record_date", action="unparseable date retained as missing", before=str(raw_dt), severity="warning"))
    elif raw_dt and str(raw_dt) != record_date.isoformat():
        audit.append(AuditEvent(field="record_date", action="normalized datetime", before=str(raw_dt), after=record_date.isoformat()))

    title = str(_first(raw, "title", "document_title", "test_name", default="Clinical record")).strip() or "Clinical record"
    text = str(_first(raw, "text", "body", "content", "note", "result", default="")).strip()
    if not text:
        audit.append(AuditEvent(field="text", action="missing content", severity="warning"))

    resource_type = _resource_type(raw)
    encounter_id = str(_first(raw, "encounter_id", "visit_id", default="")).strip() or None
    code = str(_first(raw, "code", "loinc", "test_code", default="")).strip() or None

    fingerprint_payload = "|".join([mrn, resource_type, record_date.isoformat() if record_date else "", title.lower(), text.lower()])
    fingerprint = hashlib.sha256(fingerprint_payload.encode()).hexdigest()

    return CleanRecord(
        source_id=source_id,
        patient=PatientDemographics(mrn=mrn, full_name=name, dob=dob, gender=gender),
        resource_type=resource_type,
        record_date=record_date,
        title=title,
        text=text,
        encounter_id=encounter_id,
        code=code,
        audit_log=audit,
        fingerprint=fingerprint,
    )


def _identity_key(raw: dict[str, Any]) -> tuple[str, str]:
    name = normalize_name(_first(raw, "patient_name", "name", "full_name"))
    dob = parse_date(_first(raw, "dob", "date_of_birth", "birth_date"))
    return name.lower(), dob.isoformat() if dob else ""


def clean_records(raw_records: Iterable[dict[str, Any]]) -> list[CleanRecord]:
    canonical_by_identity: dict[tuple[str, str], str] = {}
    seen_fingerprints: set[str] = set()
    output: list[CleanRecord] = []

    for raw in raw_records:
        identity = _identity_key(raw)
        incoming_mrn = normalize_mrn(_first(raw, "mrn", "patient_id", "medical_record_number"))
        canonical = canonical_by_identity.get(identity)
        if canonical is None and incoming_mrn:
            canonical_by_identity[identity] = incoming_mrn
            canonical = incoming_mrn
        record = clean_record(raw, canonical_mrn=canonical)
        canonical_by_identity.setdefault(identity, record.patient.mrn)
        if record.fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(record.fingerprint)
        output.append(record)
    return output


def load_json(path_or_text: str | Path) -> list[dict[str, Any]]:
    if isinstance(path_or_text, Path) or (isinstance(path_or_text, str) and Path(path_or_text).exists()):
        data = json.loads(Path(path_or_text).read_text(encoding="utf-8"))
    else:
        data = json.loads(str(path_or_text))
    if isinstance(data, dict):
        data = data.get("records", [data])
    if not isinstance(data, list):
        raise ValueError("JSON input must be an object, an array, or contain a 'records' array")
    return [dict(x) for x in data]


def load_csv(path_or_text: str | Path) -> list[dict[str, Any]]:
    if isinstance(path_or_text, Path) or (isinstance(path_or_text, str) and Path(path_or_text).exists()):
        text = Path(path_or_text).read_text(encoding="utf-8")
    else:
        text = str(path_or_text)
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def ingest_files(paths: Iterable[str | Path]) -> list[CleanRecord]:
    raw: list[dict[str, Any]] = []
    for p in paths:
        path = Path(p)
        if path.suffix.lower() == ".json":
            raw.extend(load_json(path))
        elif path.suffix.lower() in {".csv", ".txt"}:
            raw.extend(load_csv(path))
        else:
            raise ValueError(f"Unsupported input format: {path.suffix}")
    return clean_records(raw)
