from __future__ import annotations

import csv
import json
from pathlib import Path


PATIENTS = [
    ("Avery Demo", "12-34-56", "1985-03-14", "F"),
    ("Jordan Sample", "MRN-77-002", "1979-11-02", "M"),
    ("Morgan Test", "00003101", "1992-08-22", "U"),
    ("Casey Example", "41-00-04", "1988-01-09", "female"),
    ("Riley Mock", "MRN-55-005", "1975-06-30", "male"),
    ("Taylor Synthetic", "610006", "1990-12-11", "2"),
    ("Cameron Fixture", "MRN-71-007", "1983-04-07", "1"),
    ("Parker Sandbox", "810008", "1997-09-18", "nonbinary"),
    ("Quinn Placeholder", "91-00-09", "1968-02-26", "F"),
    ("Reese Prototype", "MRN-10-010", "2000-05-15", "M"),
    ("Skyler Dummy", "111011", "1986-07-21", "woman"),
    ("Devon Simulated", "MRN-12-012", "1972-10-03", "man"),
    ("Jamie Sandbox", "131013", "1994-03-29", "U"),
    ("Alex Mock", "MRN-14-014", "1981-08-12", "F"),
    ("Sam Demo", "151015", "1999-11-06", "M"),
    ("Drew Test", "MRN-16-016", "1965-01-17", "female"),
    ("Robin Example", "171017", "1977-05-24", "male"),
    ("Hayden Synthetic", "MRN-18-018", "1991-06-13", "2"),
    ("Blair Fixture", "191019", "1989-09-01", "1"),
    ("Emerson Sample", "MRN-20-020", "1996-12-28", "U"),
]

CONCERNS = [
    "persistent cough",
    "intermittent headache",
    "fatigue",
    "lower back pain",
    "shortness of breath",
    "abdominal discomfort",
    "dizziness",
    "sore throat",
    "knee pain",
    "palpitations",
]

CSV_FIELDS = [
    "record_id",
    "patient_name",
    "mrn",
    "dob",
    "gender",
    "record_date",
    "record_type",
    "title",
    "encounter_id",
    "text",
]


def build_raw_demo_records() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Build 62 raw synthetic records, including two deliberate duplicates."""
    json_records: list[dict[str, str]] = []
    csv_records: list[dict[str, str]] = []

    for i, (name, mrn, dob, gender) in enumerate(PATIENTS, 1):
        month = ((i - 1) % 6) + 1
        day = ((i * 2) % 25) + 1
        concern = CONCERNS[(i - 1) % len(CONCERNS)]
        encounter_id = f"enc-{i:03d}"
        date_variants = [
            f"2026-{month:02d}-{day:02d}T09:15:00",
            f"{month:02d}/{day:02d}/2026",
            f"2026/{month:02d}/{day:02d}",
            f"{month:02d}-{day:02d}-2026",
        ]

        note = {
            "id": f"doc-{i:04d}-a",
            "patient_name": name.lower() if i % 4 == 1 else name,
            "mrn": mrn,
            "dob": dob if i % 3 else dob.replace("-", "/"),
            "gender": gender,
            "record_date": date_variants[i % 4],
            "type": "discharge note" if i % 2 else "scanned note",
            "title": "Emergency Department Discharge Summary" if i % 2 else "Primary Care Progress Note",
            "encounter_id": encounter_id,
            "text": (
                f"Chief concern: {concern}. Symptoms were reviewed and supportive follow-up "
                "instructions were documented. No emergent intervention was recorded."
            ),
        }
        if i == 13:
            note.pop("id")
        json_records.append(note)

        if i % 2:
            report_type = "lab result"
            report_title = "Basic Metabolic Panel"
            report_code = "24321-2"
            report_text = (
                f"Basic laboratory panel reviewed. Sodium {137 + i % 5} mmol/L. "
                f"Potassium {3.8 + (i % 4) * 0.1:.1f} mmol/L. "
                f"Creatinine {0.8 + (i % 5) * 0.15:.2f} mg/dL."
            )
        else:
            report_type = "imaging report"
            report_title = "Chest X-ray Report"
            report_code = "36643-5"
            report_text = (
                f"Chest radiograph reviewed for {concern}. Mild nonspecific basilar linear opacity "
                "is described. No pleural effusion reported."
            )
        if i in (4, 12):
            report_text += " Result flagged high by the reporting system."

        json_records.append(
            {
                "id": f"rep-{i:04d}-b",
                "patient_name": name,
                "patient_id": mrn.replace("-", "") if mrn.replace("-", "").isdigit() else mrn,
                "dob": dob,
                "sex": gender,
                "timestamp": f"2026-{month:02d}-{min(day + 1, 28):02d}T14:30:00Z",
                "record_type": report_type,
                "title": report_title,
                "code": report_code,
                "encounter_id": encounter_id,
                "text": report_text,
            }
        )

        followup_mrn = mrn
        if i in (3, 8, 13, 18):
            followup_mrn = ""
        if i in (5, 9, 17):
            followup_mrn = str(90000000 + i)
        normalized_gender = {
            "F": "female",
            "M": "male",
            "U": "unknown",
            "female": "F",
            "male": "M",
            "2": "F",
            "1": "M",
            "nonbinary": "other",
        }.get(gender, gender)
        followup_date = (
            f"{month:02d}/{min(day + 2, 28):02d}/2026"
            if i % 3 == 1
            else f"2026-{month:02d}-{min(day + 2, 28):02d}"
        )
        csv_records.append(
            {
                "record_id": f"note-{i:04d}-c",
                "patient_name": name,
                "mrn": followup_mrn,
                "dob": dob,
                "gender": normalized_gender,
                "record_date": followup_date,
                "record_type": "scanned note",
                "title": "Follow-up Note",
                "encounter_id": encounter_id,
                "text": (
                    f"Follow-up for {concern}. Prior records were reviewed. Symptoms are stable or "
                    "improving; outpatient follow-up was recommended."
                ),
            }
        )

    duplicate_json = dict(json_records[3])
    duplicate_json["id"] = "duplicate-json-0002"
    json_records.append(duplicate_json)
    duplicate_csv = dict(csv_records[6])
    duplicate_csv["record_id"] = "duplicate-csv-0007"
    csv_records.append(duplicate_csv)
    return json_records, csv_records


def write_demo_corpus(data_dir: str | Path) -> tuple[Path, Path]:
    """Write the deterministic, reviewable JSON and CSV assessment inputs."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    json_records, csv_records = build_raw_demo_records()
    json_path = data_dir / "sample_ehr.json"
    csv_path = data_dir / "sample_notes.csv"
    json_path.write_text(json.dumps({"records": json_records}, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(csv_records)
    return json_path, csv_path
