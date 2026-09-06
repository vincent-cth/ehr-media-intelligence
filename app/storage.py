from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .models import CleanRecord


SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    dob TEXT,
    gender TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    record_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    record_date TEXT,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    audit_json TEXT NOT NULL,
    FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
);
CREATE INDEX IF NOT EXISTS idx_records_patient ON records(patient_id);
CREATE INDEX IF NOT EXISTS idx_records_filters ON records(resource_type, record_date);
CREATE TABLE IF NOT EXISTS bundles (
    patient_id TEXT PRIMARY KEY,
    bundle_json TEXT NOT NULL,
    valid INTEGER NOT NULL,
    validation_errors TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS summaries (
    patient_id TEXT PRIMARY KEY,
    record_hash TEXT NOT NULL,
    summary_json TEXT NOT NULL
);
"""


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @staticmethod
    def _save_records(conn: sqlite3.Connection, records: Iterable[CleanRecord]) -> None:
        for record in records:
            patient = record.patient
            conn.execute(
                "INSERT OR REPLACE INTO patients(patient_id,name,dob,gender) VALUES (?,?,?,?)",
                (
                    patient.mrn,
                    patient.full_name,
                    patient.dob.isoformat() if patient.dob else None,
                    patient.gender,
                ),
            )
            conn.execute(
                """INSERT OR REPLACE INTO records(
                    record_id,patient_id,resource_type,record_date,title,text,fingerprint,audit_json
                ) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    record.source_id,
                    patient.mrn,
                    record.resource_type,
                    record.record_date.isoformat() if record.record_date else None,
                    record.title,
                    record.text,
                    record.fingerprint,
                    json.dumps([event.model_dump() for event in record.audit_log]),
                ),
            )

    def save_records(self, records: list[CleanRecord]) -> None:
        with self.connect() as conn:
            self._save_records(conn, records)

    def replace_records(self, records: list[CleanRecord]) -> None:
        """Replace the demo dataset atomically while preserving reusable summary cache rows."""
        with self.connect() as conn:
            conn.execute("DELETE FROM bundles")
            conn.execute("DELETE FROM records")
            conn.execute("DELETE FROM patients")
            self._save_records(conn, records)
            patient_ids = sorted({record.patient.mrn for record in records})
            if patient_ids:
                placeholders = ",".join("?" for _ in patient_ids)
                conn.execute(f"DELETE FROM summaries WHERE patient_id NOT IN ({placeholders})", patient_ids)
            else:
                conn.execute("DELETE FROM summaries")

    def save_bundle(self, patient_id: str, bundle: dict[str, Any], valid: bool, errors: list[str]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO bundles(patient_id,bundle_json,valid,validation_errors) VALUES (?,?,?,?)",
                (patient_id, json.dumps(bundle), int(valid), json.dumps(errors)),
            )

    def get_bundle(self, patient_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT bundle_json FROM bundles WHERE patient_id=?", (patient_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def get_bundle_validation(self, patient_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT valid,validation_errors FROM bundles WHERE patient_id=?", (patient_id,)
            ).fetchone()
        if not row:
            return None
        return {"valid": bool(row["valid"]), "errors": json.loads(row["validation_errors"])}

    def list_bundle_validations(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT patient_id,valid,validation_errors FROM bundles ORDER BY patient_id"
            ).fetchall()
        return [
            {
                "patient_id": row["patient_id"],
                "valid": bool(row["valid"]),
                "errors": json.loads(row["validation_errors"]),
            }
            for row in rows
        ]

    def list_patients(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT patient_id,name,dob,gender FROM patients ORDER BY name"
            ).fetchall()
        return [dict(row) for row in rows]

    def patient_records(self, patient_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM records WHERE patient_id=? ORDER BY record_date DESC", (patient_id,)
            ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["audit_log"] = json.loads(item.pop("audit_json"))
            output.append(item)
        return output

    def all_records(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT r.*, p.name AS patient_name, s.summary_json
                FROM records r
                JOIN patients p ON p.patient_id=r.patient_id
                LEFT JOIN summaries s ON s.patient_id=r.patient_id
                ORDER BY r.record_date DESC"""
            ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            raw_summary = item.pop("summary_json", None)
            item["summary_snippet"] = ""
            item["summary_confidence"] = None
            if raw_summary:
                try:
                    summary = json.loads(raw_summary)
                    item["summary_snippet"] = summary.get("narrative", "")
                    item["summary_confidence"] = summary.get("confidence")
                except json.JSONDecodeError:
                    pass
            output.append(item)
        return output

    def counts(self) -> dict[str, int]:
        with self.connect() as conn:
            patients = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
            records = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            valid_bundles = conn.execute("SELECT COUNT(*) FROM bundles WHERE valid=1").fetchone()[0]
            bundles = conn.execute("SELECT COUNT(*) FROM bundles").fetchone()[0]
        return {
            "patients": patients,
            "records": records,
            "bundles": bundles,
            "valid_bundles": valid_bundles,
        }

    def save_summary(self, patient_id: str, record_hash: str, summary: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO summaries(patient_id,record_hash,summary_json) VALUES (?,?,?)",
                (patient_id, record_hash, json.dumps(summary)),
            )

    def get_cached_summary(self, patient_id: str, record_hash: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT summary_json FROM summaries WHERE patient_id=? AND record_hash=?",
                (patient_id, record_hash),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def latest_summary(self, patient_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT summary_json FROM summaries WHERE patient_id=?", (patient_id,)).fetchone()
        return json.loads(row[0]) if row else None
