# EHR Media Intelligence Platform

An AI full-stack assessment implementation that turns messy synthetic EHR media into validated FHIR R4 Bundles, source-grounded clinical summaries, and sub-second semantic search. The stack is Python 3.11+, FastAPI, Pydantic v2, SQLite, sentence-transformers, FAISS, Tailwind CSS, and vanilla JavaScript.

> Safety: every included patient and record is synthetic. AI summaries support information retrieval only and are not clinical decisions or diagnoses.

## Assessment coverage

| Requirement | Implementation and evidence |
|---|---|
| Ingestion and cleaning | JSON + CSV/TXT loaders; normalized MRN, DOB, gender, names, and UTC dates; missing-field handling; identity-conflict resolution; content fingerprint deduplication; Pydantic models with per-record audit events |
| FHIR R4 | Patient, Encounter, DocumentReference, and DiagnosticReport resources; patient-level collection Bundles; exact R4 4.0.1 validation with `fhirclient`, Pydantic validation with `fhir.resources`, and explicit reference-integrity checks |
| AI summaries | OpenAI-compatible API integration configured for DeepSeek; six-field structured JSON; source-only prompt; hard 200-word clinical budget; confidence, model, generation method, and disclaimer; SQLite cache keyed by patient + Bundle hash |
| Semantic search | `all-MiniLM-L6-v2` embeddings over source text plus AI summaries; FAISS cosine ranking; strict resource/date pre-filtering; top five results with scores and summary/source snippets |
| Frontend | Debounced real-time search; filters; ranked cards; AI summary snippets; patient modal with full summary, linked FHIR resources, validation status and cleaning audit trail; responsive, loading, error and empty states; ARIA/live regions and keyboard navigation |

The deterministic demo creates **62 raw records**, deliberately including two duplicates and multiple cleaning edge cases. Ingestion produces **60 unique records across 20 synthetic patients**.

## Quick start

### Windows PowerShell

```powershell
python -m venv .venv
Copy-Item .env.example .env
# Add your API key to OPENAI_API_KEY in .env.
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\bootstrap.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### macOS / Linux

```bash
python3 -m venv .venv
cp .env.example .env
# Add your API key to OPENAI_API_KEY in .env.
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/bootstrap.py
.venv/bin/python -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. Interactive API documentation is available at <http://127.0.0.1:8000/docs>. Stop the development server with `Ctrl+C`.

The first run downloads `sentence-transformers/all-MiniLM-L6-v2`; later runs use the local Hugging Face cache. `.env`, the generated corpus, SQLite database, FHIR report, and FAISS files live outside version control.

## LLM configuration

The project uses the OpenAI Python SDK with an OpenAI-compatible endpoint. The supplied `.env.example` targets DeepSeek:

```dotenv
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash
```

For DeepSeek V4, summarization disables thinking mode for reliable structured JSON and retries one occasional empty JSON response. If the API is unavailable, a logged, visibly low-confidence extractive fallback keeps the demo usable. A fallback cache is retried automatically when an API key becomes available.

## Run the pipeline

```powershell
.\.venv\Scripts\python.exe scripts\bootstrap.py
```

Expected shape:

```text
{'raw_records': 62, 'records': 60, 'duplicates_removed': 2,
 'patients': 20, 'valid_bundles': 20, 'indexed_records': 60}
```

Bootstrap performs the complete pipeline and fails clearly if any FHIR Bundle is invalid. It writes the detailed validation report to `artifacts/fhir_validation_report.json`.

```text
generated JSON + CSV
        |
        v
Pydantic cleaning + audit trail + deduplication
        |
        v
Patient-level FHIR R4 Bundles
        |----> exact R4 + Pydantic + reference validation ----> SQLite/report
        |----> cached, source-grounded LLM summaries ----------> SQLite
        +----> source text + summaries -> MiniLM -> FAISS
                                                    |
                                                    v
                                          FastAPI -> Tailwind UI
```

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Record, patient, Bundle and search-backend status |
| `POST` | `/search` | Top-five semantic matches; optional `resource_type`, `date_from`, `date_to` query filters |
| `GET` | `/patients/{patient_id}` | Patient summary, source records/audit trails, FHIR Bundle and validation result |
| `GET` | `/fhir/validation` | Human- and machine-readable validation results for every Bundle |
| `POST` | `/admin/rebuild-search` | Rebuild and persist the FAISS index |

Example:

```bash
curl -X POST "http://127.0.0.1:8000/search?resource_type=DiagnosticReport&date_from=2026-01-01" \
  -H "Content-Type: application/json" \
  -d '{"query":"chest imaging with basilar opacity"}'
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\benchmark_search.py
.\.venv\Scripts\python.exe scripts\build_writeup_pdf.py
```

Tests cover cleaning edge cases, the 60-record corpus, R4 schema/reference validation, summary caching and retry behavior, the 200-word limit and disclaimer, filter-before-ranking behavior, and FastAPI endpoints. On the current development machine, a warm 50-record semantic query completes in approximately `0.006s`, comfortably below the two-second target; rerun the benchmark for machine-specific evidence.

## Key decisions and tradeoffs

1. **Auditable normalization.** Corrections are explicit `AuditEvent` values rather than opaque mutation. Name + DOB identity reconciliation is intentionally conservative and is not a production master-patient-index algorithm.
2. **Dual FHIR validation.** `fhirclient` supplies exact R4 4.0.1 models; `fhir.resources` preserves the required Pydantic-v2 workflow through its R4B namespace, which its maintainers position as the supported overlap for R4-era content. Reference resolution is checked separately because schema validation alone cannot prove local targets exist.
3. **Source-grounded summaries.** The prompt forbids inferred diagnoses, anomaly text must remain tied to reported findings, output has a hard word budget, and the UI always shows the disclaimer and source record beside the summary.
4. **FAISS with pre-filtering.** Exact metadata filtering precedes ranking so narrow filters still return the true top five. This is simple and fast for assessment scale; production retrieval would add lexical search and reranking.
5. **Reproducible synthetic evaluation data.** Generated JSON and CSV inputs exercise date, gender, MRN, missing-field, duplicate and identifier-conflict paths without committing real patient data.

## Production improvements

- Official HL7 validator/terminology server, US Core profiles, and LOINC/SNOMED normalization
- OCR/PDF extraction, object storage, MIME-aware attachments, provenance, and claim-level citations
- Authentication, RBAC, encryption, secret management, access logs, retention controls, and PHI review
- Background ingestion, incremental index updates, hybrid retrieval/reranking, observability and load tests
- Clinician-reviewed gold summaries with factuality, omission, hallucination, and anomaly-recall metrics

See [WRITEUP.md](WRITEUP.md) and the generated `WRITEUP.pdf` for the one-page submission narrative.
