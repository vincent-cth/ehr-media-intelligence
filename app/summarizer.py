from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from .config import settings
from .fhir_mapper import bundle_text
from .models import ClinicalSummary
from .storage import SQLiteStore

SYSTEM_PROMPT = """You summarize synthetic EHR media for a retrieval interface. Return JSON only with keys: chief_concern, key_diagnoses, recent_media_records, flagged_anomalies, narrative, confidence. Be conservative: do not invent diagnoses or abnormal findings. Narrative must be concise; entire response should remain under 200 words. confidence must be low, medium, or high."""


def record_hash(bundle: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(bundle, sort_keys=True).encode()).hexdigest()


def _extractive_fallback(patient_id: str, text: str) -> ClinicalSummary:
    lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines() if x.strip()]
    joined = " ".join(lines)
    anomaly_terms = re.findall(r"[^.]{0,60}\b(abnormal|elevated|low|high|critical|nodule|opacity|positive|negative)\b[^.]{0,80}", joined, flags=re.I)
    anomalies = []
    if anomaly_terms:
        anomalies = ["Source records contain language that may indicate an abnormal or notable finding; review the linked record."]
    narrative = (joined[:700] + ("..." if len(joined) > 700 else "")) or "No narrative content available."
    return ClinicalSummary(patient_id=patient_id,chief_concern=lines[0][:140] if lines else "Not stated in available records",key_diagnoses=[],recent_media_records=lines[:3],flagged_anomalies=anomalies,narrative=narrative,confidence="low")


def summarize_bundle(patient_id: str, bundle: dict[str, Any], store: SQLiteStore, force: bool = False) -> ClinicalSummary:
    digest = record_hash(bundle)
    if not force:
        cached = store.get_cached_summary(patient_id, digest)
        if cached:
            return ClinicalSummary.model_validate(cached)
    text = bundle_text(bundle)
    api_key = os.getenv("OPENAI_API_KEY")
    summary: ClinicalSummary
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=settings.openai_base_url)
            response = client.chat.completions.create(model=settings.openai_model,temperature=0,response_format={"type": "json_object"},messages=[{"role": "system", "content": SYSTEM_PROMPT},{"role": "user", "content": f"Patient ID: {patient_id}\nFHIR media text:\n{text[:12000]}"}])
            payload = json.loads(response.choices[0].message.content or "{}")
            summary = ClinicalSummary(patient_id=patient_id, **payload)
        except Exception:
            summary = _extractive_fallback(patient_id, text)
    else:
        summary = _extractive_fallback(patient_id, text)
    words = summary.narrative.split()
    if len(words) > 120:
        summary.narrative = " ".join(words[:120]) + "..."
    store.save_summary(patient_id, digest, summary.model_dump())
    return summary
