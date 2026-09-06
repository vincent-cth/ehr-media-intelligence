from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


ResourceKind = Literal["DocumentReference", "DiagnosticReport"]


class AuditEvent(BaseModel):
    field: str
    action: str
    before: str | None = None
    after: str | None = None
    severity: Literal["info", "warning", "error"] = "info"


class PatientDemographics(BaseModel):
    mrn: str
    full_name: str
    dob: date | None = None
    gender: Literal["male", "female", "other", "unknown"] = "unknown"


class CleanRecord(BaseModel):
    source_id: str
    patient: PatientDemographics
    resource_type: ResourceKind
    record_date: datetime | None = None
    title: str
    text: str
    encounter_id: str | None = None
    code: str | None = None
    audit_log: list[AuditEvent] = Field(default_factory=list)
    fingerprint: str


class ClinicalSummary(BaseModel):
    patient_id: str
    chief_concern: str
    key_diagnoses: list[str]
    recent_media_records: list[str]
    flagged_anomalies: list[str]
    narrative: str
    confidence: Literal["low", "medium", "high"]
    disclaimer: str = "AI-generated summary for information retrieval only; not a clinical decision or diagnosis."
    generation_method: Literal["llm", "extractive_fallback"] = "extractive_fallback"
    model: str | None = None


class SearchHit(BaseModel):
    patient_id: str
    patient_name: str
    mrn: str
    record_id: str
    record_date: str | None
    resource_type: str
    title: str
    score: float
    snippet: str
    record_excerpt: str
