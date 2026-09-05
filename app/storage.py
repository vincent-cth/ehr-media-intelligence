from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import CleanRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (patient_id TEXT PRIMARY KEY,name TEXT NOT NULL,dob TEXT,gender TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS records (record_id TEXT PRIMARY KEY,patient_id TEXT NOT NULL,resource_type TEXT NOT NULL,record_date TEXT,title TEXT NOT NULL,text TEXT NOT NULL,fingerprint TEXT NOT NULL,audit_json TEXT NOT NULL,FOREIGN KEY(patient_id) REFERENCES patients(patient_id));
CREATE TABLE IF NOT EXISTS bundles (patient_id TEXT PRIMARY KEY,bundle_json TEXT NOT NULL,valid INTEGER NOT NULL,validation_errors TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS summaries (patient_id TEXT PRIMARY KEY,record_hash TEXT NOT NULL,summary_json TEXT NOT NULL);
"""

class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True); self.init()
    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path); conn.row_factory = sqlite3.Row; return conn
    def init(self) -> None:
        with self.connect() as conn: conn.executescript(SCHEMA)
    def save_records(self, records: list[CleanRecord]) -> None:
        with self.connect() as conn:
            for r in records:
                p=r.patient
                conn.execute("INSERT OR REPLACE INTO patients(patient_id,name,dob,gender) VALUES (?,?,?,?)",(p.mrn,p.full_name,p.dob.isoformat() if p.dob else None,p.gender))
                conn.execute("INSERT OR REPLACE INTO records(record_id,patient_id,resource_type,record_date,title,text,fingerprint,audit_json) VALUES (?,?,?,?,?,?,?,?)",(r.source_id,p.mrn,r.resource_type,r.record_date.isoformat() if r.record_date else None,r.title,r.text,r.fingerprint,json.dumps([a.model_dump() for a in r.audit_log])))
    def save_bundle(self, patient_id: str, bundle: dict[str, Any], valid: bool, errors: list[str]) -> None:
        with self.connect() as conn: conn.execute("INSERT OR REPLACE INTO bundles(patient_id,bundle_json,valid,validation_errors) VALUES (?,?,?,?)",(patient_id,json.dumps(bundle),int(valid),json.dumps(errors)))
    def get_bundle(self, patient_id: str) -> dict[str, Any] | None:
        with self.connect() as conn: row=conn.execute("SELECT bundle_json FROM bundles WHERE patient_id=?",(patient_id,)).fetchone()
        return json.loads(row[0]) if row else None
    def list_patients(self) -> list[dict[str, Any]]:
        with self.connect() as conn: rows=conn.execute("SELECT patient_id,name,dob,gender FROM patients ORDER BY name").fetchall()
        return [dict(r) for r in rows]
    def patient_records(self, patient_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn: rows=conn.execute("SELECT * FROM records WHERE patient_id=? ORDER BY record_date DESC",(patient_id,)).fetchall()
        return [dict(r) for r in rows]
    def all_records(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows=conn.execute("SELECT r.*, p.name AS patient_name, s.summary_json FROM records r JOIN patients p ON p.patient_id=r.patient_id LEFT JOIN summaries s ON s.patient_id=r.patient_id ORDER BY r.record_date DESC").fetchall()
        output=[]
        for row in rows:
            item=dict(row); raw_summary=item.pop("summary_json",None)
            if raw_summary:
                try: item["summary_snippet"]=json.loads(raw_summary).get("narrative","")
                except json.JSONDecodeError: item["summary_snippet"]=""
            else: item["summary_snippet"]=""
            output.append(item)
        return output
    def save_summary(self, patient_id: str, record_hash: str, summary: dict[str, Any]) -> None:
        with self.connect() as conn: conn.execute("INSERT OR REPLACE INTO summaries(patient_id,record_hash,summary_json) VALUES (?,?,?)",(patient_id,record_hash,json.dumps(summary)))
    def get_cached_summary(self, patient_id: str, record_hash: str) -> dict[str, Any] | None:
        with self.connect() as conn: row=conn.execute("SELECT summary_json FROM summaries WHERE patient_id=? AND record_hash=?",(patient_id,record_hash)).fetchone()
        return json.loads(row[0]) if row else None
    def latest_summary(self, patient_id: str) -> dict[str, Any] | None:
        with self.connect() as conn: row=conn.execute("SELECT summary_json FROM summaries WHERE patient_id=?",(patient_id,)).fetchone()
        return json.loads(row[0]) if row else None
