from __future__ import annotations

import base64
import json
import re
from collections import defaultdict
from typing import Any

from .models import CleanRecord


def _safe_id(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9.-]", "-", value)
    return value[:64] or "unknown"


def patient_resource(record: CleanRecord) -> dict[str, Any]:
    p = record.patient
    parts = p.full_name.split()
    return {
        "resourceType": "Patient",
        "id": _safe_id(p.mrn),
        "identifier": [{"system": "urn:example:mrn", "value": p.mrn}],
        "name": [{"text": p.full_name, "family": parts[-1] if parts else p.full_name, "given": parts[:-1] or [p.full_name]}],
        **({"birthDate": p.dob.isoformat()} if p.dob else {}),
        "gender": p.gender,
    }


def encounter_resource(record: CleanRecord) -> dict[str, Any]:
    encounter_id = _safe_id(record.encounter_id or f"enc-{record.source_id}")
    resource: dict[str, Any] = {
        "resourceType": "Encounter",
        "id": encounter_id,
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
        "subject": {"reference": f"Patient/{_safe_id(record.patient.mrn)}"},
    }
    if record.record_date:
        resource["period"] = {"start": record.record_date.isoformat()}
    return resource


def document_reference_resource(record: CleanRecord) -> dict[str, Any]:
    enc_id = _safe_id(record.encounter_id or f"enc-{record.source_id}")
    content = base64.b64encode(record.text.encode()).decode()
    return {
        "resourceType": "DocumentReference",
        "id": _safe_id(record.source_id),
        "status": "current",
        "subject": {"reference": f"Patient/{_safe_id(record.patient.mrn)}"},
        "context": {"encounter": [{"reference": f"Encounter/{enc_id}"}]},
        "date": record.record_date.isoformat() if record.record_date else None,
        "description": record.title,
        "content": [{"attachment": {"contentType": "text/plain", "data": content, "title": record.title}}],
    }


def diagnostic_report_resource(record: CleanRecord) -> dict[str, Any]:
    enc_id = _safe_id(record.encounter_id or f"enc-{record.source_id}")
    resource: dict[str, Any] = {
        "resourceType": "DiagnosticReport",
        "id": _safe_id(record.source_id),
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": record.code or "LP29684-5", "display": record.title}], "text": record.title},
        "subject": {"reference": f"Patient/{_safe_id(record.patient.mrn)}"},
        "encounter": {"reference": f"Encounter/{enc_id}"},
        "conclusion": record.text[:4000],
    }
    if record.record_date:
        resource["effectiveDateTime"] = record.record_date.isoformat()
        resource["issued"] = record.record_date.isoformat()
    return resource


def build_bundles(records: list[CleanRecord]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[CleanRecord]] = defaultdict(list)
    for record in records:
        grouped[record.patient.mrn].append(record)

    bundles: dict[str, dict[str, Any]] = {}
    for mrn, rows in grouped.items():
        first = rows[0]
        entries: list[dict[str, Any]] = [{"resource": patient_resource(first)}]
        encounters: set[str] = set()
        for row in rows:
            enc = encounter_resource(row)
            if enc["id"] not in encounters:
                entries.append({"resource": enc})
                encounters.add(enc["id"])
            if row.resource_type == "DiagnosticReport":
                resource = diagnostic_report_resource(row)
            else:
                resource = document_reference_resource(row)
            resource = {k: v for k, v in resource.items() if v is not None}
            entries.append({"resource": resource})
        bundles[mrn] = {
            "resourceType": "Bundle",
            "id": f"bundle-{_safe_id(mrn)}",
            "type": "collection",
            "entry": entries,
        }
    return bundles


def validate_bundle(bundle: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        from fhir.resources.R4B.bundle import Bundle
        validator = getattr(Bundle, "model_validate", None)
        if validator:
            validator(bundle)
        else:
            Bundle.parse_obj(bundle)
    except ImportError:
        return False, ["fhir.resources is not installed; run pip install -r requirements.txt"]
    except Exception as exc:
        errors.append(str(exc))

    resources = [e.get("resource", {}) for e in bundle.get("entry", [])]
    ids = {f"{r.get('resourceType')}/{r.get('id')}" for r in resources if r.get("resourceType") and r.get("id")}
    for r in resources:
        for field in ("subject", "encounter"):
            ref = r.get(field)
            refs = []
            if isinstance(ref, dict) and ref.get("reference"):
                refs = [ref["reference"]]
            if field == "encounter" and isinstance(ref, list):
                refs = [x.get("reference") for x in ref if isinstance(x, dict)]
            for target in refs:
                if target and target not in ids:
                    errors.append(f"Broken {field} reference: {target}")
        context = r.get("context", {})
        for enc in context.get("encounter", []) if isinstance(context, dict) else []:
            target = enc.get("reference") if isinstance(enc, dict) else None
            if target and target not in ids:
                errors.append(f"Broken context.encounter reference: {target}")
    return not errors, errors


def validation_report(bundles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    report: dict[str, Any] = {"valid": True, "patients": {}}
    for patient_id, bundle in bundles.items():
        ok, errors = validate_bundle(bundle)
        report["patients"][patient_id] = {"valid": ok, "errors": errors}
        report["valid"] = report["valid"] and ok
    return report


def bundle_text(bundle: dict[str, Any]) -> str:
    chunks: list[str] = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType")
        if rtype == "DocumentReference":
            for item in resource.get("content", []):
                att = item.get("attachment", {})
                if att.get("title"):
                    chunks.append(att["title"])
                if att.get("data"):
                    try:
                        chunks.append(base64.b64decode(att["data"]).decode(errors="replace"))
                    except Exception:
                        pass
        elif rtype == "DiagnosticReport":
            chunks.append(resource.get("code", {}).get("text", "Diagnostic report"))
            chunks.append(resource.get("conclusion", ""))
    return "\n".join(x for x in chunks if x)
