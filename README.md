# EHR Media Intelligence Platform

AI full-stack assessment implementation: Python/FastAPI backend, Pydantic cleaning layer, HL7 FHIR resources, OpenAI clinical summarization, sentence-transformer + FAISS semantic search, SQLite persistence, and a Tailwind clinician-facing UI. **All included records are synthetic.**

## What is implemented

- **Task 1 - ingestion & cleaning:** JSON and CSV/TXT ingestion; missing-field handling; multiple date formats; duplicate removal; MRN/gender/DOB normalization; identity-conflict resolution; Pydantic intermediate models; per-record audit log; pytest edge cases.
- **Task 2 - FHIR R4 normalization:** Patient, Encounter, DocumentReference, and DiagnosticReport resources; patient-level Bundle; subject/encounter references; `fhir.resources` R4B compatibility models plus explicit reference-integrity checks; SQLite Bundle storage.
- **Task 3 - AI summarization:** OpenAI API integration with JSON-constrained prompt, <200-word design target, patient+Bundle-hash caching, confidence and non-clinical-decision disclaimer. A low-confidence extractive fallback keeps the demo runnable when no API key is configured.
- **Task 4 - semantic search:** `sentence-transformers/all-MiniLM-L6-v2` embeddings, FAISS inner-product index, `POST /search`, top-5 ranking, FHIR resource/date filters, persistent index metadata.
- **Task 5 - frontend:** Tailwind CSS + vanilla JS; realtime search; ranked result cards; patient summary/FHIR detail modal; date/resource filters; responsive/empty/loading states; keyboard-focusable results and ARIA labels.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/bootstrap.py
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. The app uses only synthetic records from `data/`.

> If the embedding model is not already cached, the first run downloads `all-MiniLM-L6-v2`. If `OPENAI_API_KEY` is absent, summaries use the low-confidence offline fallback.

## API

### Search

```bash
curl -X POST 'http://127.0.0.1:8000/search?resource_type=DiagnosticReport&date_from=2026-01-01' \
  -H 'Content-Type: application/json' \
  -d '{"query":"chest imaging opacity"}'
```

Returns up to five ranked matches with relevance scores.

### Patient detail

```bash
curl http://127.0.0.1:8000/patients/00123456
```

Returns the cached AI summary, linked source records, and full FHIR Bundle.

### Health / rebuild

- `GET /health`
- `POST /admin/rebuild-search`

## Data pipeline

```text
JSON / CSV
   |
   v
Pydantic cleaning + audit log
   |
   v
Patient-level FHIR Bundle
   |----> fhir.resources validation + reference checks
   |
   +----> SQLite
   |
   +----> OpenAI summary -> hash cache
   |
   +----> SentenceTransformer -> FAISS
                              |
                              v
                         POST /search
                              |
                              v
                    Tailwind clinician UI
```

## Tests

```bash
pytest
python scripts/benchmark_search.py
```

The tests cover inconsistent date/gender/MRN normalization, missing identifiers, duplicate removal, conflicting MRNs, FHIR resource/reference construction, and filtered semantic search. The benchmark constructs 50 synthetic records and asserts a search completes in under two seconds on the active embedding backend.

## Key design decisions

1. **Auditable cleaning over opaque repair.** Every material normalization/change is retained as an `AuditEvent`.
2. **Patient-level Bundle storage.** This makes downstream summarization and detail retrieval straightforward.
3. **Reference checks beyond schema checks.** FHIR schema validation does not prove that `Patient/...` or `Encounter/...` references resolve within the Bundle, so the project checks both.
4. **API-first AI with safe demo fallback.** The OpenAI path satisfies the LLM requirement; the offline fallback is explicitly lower confidence and prevents a missing key from making the evaluator unable to run the app.
5. **FAISS for a small local corpus.** It is simple and fast for the assessment scale; metadata filters are applied after over-retrieval.

## Production improvements

- Official HL7 R4 validator / terminology server; LOINC and SNOMED normalization.
- OCR + robust PDF extraction, MIME-aware DocumentReference content, and object storage.
- Enterprise MPI/patient matching instead of demo name+DOB matching.
- PHI controls: authentication, RBAC, encryption, access logs, retention policy, secret management.
- Hybrid lexical/vector retrieval and cross-encoder reranking.
- Clinician-reviewed summary evaluation set, claim-level provenance, and hallucination monitoring.
- Async job queue, containerization, CI/CD, observability, and load testing.

See `WRITEUP.md` for the one-page submission narrative.
