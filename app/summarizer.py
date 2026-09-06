from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any

from .config import settings
from .fhir_mapper import bundle_text
from .models import ClinicalSummary
from .storage import SQLiteStore


logger = logging.getLogger(__name__)
PROMPT_VERSION = "clinical-summary-v2"
MAX_CLINICAL_WORDS = 200
SYSTEM_PROMPT = """You summarize synthetic FHIR R4 EHR media for clinical information retrieval.
Return one JSON object only, with exactly these keys: chief_concern, key_diagnoses,
recent_media_records, flagged_anomalies, narrative, confidence.

Rules:
- Use only facts explicitly present in the supplied records. Never infer a diagnosis.
- If a requested item is absent, use "Not stated" or an empty list.
- For anomalies, state the source record or test and the reported finding; do not reinterpret it.
- Keep all clinical fields combined under 200 words.
- confidence must be low, medium, or high and reflect source completeness, not medical certainty.

Example JSON shape:
{"chief_concern":"Not stated","key_diagnoses":[],"recent_media_records":[],
"flagged_anomalies":[],"narrative":"Concise source-grounded summary.","confidence":"low"}
"""


def record_hash(bundle: dict[str, Any]) -> str:
    payload = f"{PROMPT_VERSION}\n{json.dumps(bundle, sort_keys=True, separators=(',', ':'))}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _trim_words(value: str, limit: int) -> str:
    words = re.sub(r"\s+", " ", value).strip().split()
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]) + "..."


def _trim_list(values: list[str], word_limit: int, item_limit: int = 5) -> list[str]:
    remaining = word_limit
    output: list[str] = []
    for value in values[:item_limit]:
        if remaining <= 0:
            break
        trimmed = _trim_words(str(value), remaining)
        used = len(trimmed.removesuffix("...").split())
        if trimmed:
            output.append(trimmed)
            remaining -= used
    return output


def clinical_word_count(summary: ClinicalSummary) -> int:
    values = [summary.chief_concern, summary.narrative]
    values.extend(summary.key_diagnoses)
    values.extend(summary.recent_media_records)
    values.extend(summary.flagged_anomalies)
    return sum(len(value.removesuffix("...").split()) for value in values)


def enforce_word_budget(summary: ClinicalSummary) -> ClinicalSummary:
    summary.chief_concern = _trim_words(summary.chief_concern, 25)
    summary.key_diagnoses = _trim_list(summary.key_diagnoses, 30)
    summary.recent_media_records = _trim_list(summary.recent_media_records, 40)
    summary.flagged_anomalies = _trim_list(summary.flagged_anomalies, 35)
    used = clinical_word_count(summary) - len(summary.narrative.split())
    summary.narrative = _trim_words(summary.narrative, max(1, MAX_CLINICAL_WORDS - used))
    return summary


def _extractive_fallback(patient_id: str, text: str) -> ClinicalSummary:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
    joined = " ".join(lines)
    has_anomaly_language = re.search(
        r"\b(abnormal|elevated|low|high|critical|nodule|opacity|positive)\b",
        joined,
        flags=re.I,
    )
    anomalies = []
    if has_anomaly_language:
        anomalies = [
            "Source records contain potentially notable result language; review the linked record."
        ]
    summary = ClinicalSummary(
        patient_id=patient_id,
        chief_concern=lines[0] if lines else "Not stated in available records",
        key_diagnoses=[],
        recent_media_records=lines[:3],
        flagged_anomalies=anomalies,
        narrative=joined or "No narrative content available.",
        confidence="low",
        generation_method="extractive_fallback",
        model=None,
    )
    return enforce_word_budget(summary)


def summarize_bundle(
    patient_id: str,
    bundle: dict[str, Any],
    store: SQLiteStore,
    force: bool = False,
) -> ClinicalSummary:
    digest = record_hash(bundle)
    api_key = os.getenv("OPENAI_API_KEY")
    if not force:
        cached = store.get_cached_summary(patient_id, digest)
        if cached:
            cached_summary = ClinicalSummary.model_validate(cached)
            if not api_key or cached_summary.generation_method == "llm":
                return cached_summary

    text = bundle_text(bundle)
    summary: ClinicalSummary
    if api_key:
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=settings.openai_base_url,
                timeout=30,
            )
            request_options: dict[str, Any] = {}
            if settings.openai_base_url and "deepseek.com" in settings.openai_base_url:
                request_options["extra_body"] = {"thinking": {"type": "disabled"}}
            payload: dict[str, Any] = {}
            required_fields = {
                "chief_concern",
                "key_diagnoses",
                "recent_media_records",
                "flagged_anomalies",
                "narrative",
                "confidence",
            }
            for attempt in range(2):
                response = client.chat.completions.create(
                    model=settings.openai_model,
                    temperature=0,
                    max_tokens=700,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"Patient ID: {patient_id}\nFHIR media text:\n{text[:12000]}\n"
                                + ("Return the complete JSON object now." if attempt else "")
                            ),
                        },
                    ],
                    **request_options,
                )
                content = (response.choices[0].message.content or "").strip()
                if content:
                    payload = json.loads(content)
                if required_fields.issubset(payload):
                    break
            missing = sorted(required_fields - payload.keys())
            if missing:
                raise ValueError(f"LLM returned incomplete JSON; missing: {', '.join(missing)}")
            payload.pop("patient_id", None)
            payload.pop("generation_method", None)
            payload.pop("model", None)
            summary = ClinicalSummary(
                patient_id=patient_id,
                generation_method="llm",
                model=settings.openai_model,
                **payload,
            )
            summary = enforce_word_budget(summary)
        except Exception as exc:
            logger.warning(
                "LLM summary failed for patient %s; using extractive fallback (%s: %s)",
                patient_id,
                type(exc).__name__,
                exc,
            )
            summary = _extractive_fallback(patient_id, text)
    else:
        summary = _extractive_fallback(patient_id, text)

    store.save_summary(patient_id, digest, summary.model_dump())
    return summary
