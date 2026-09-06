# EHR Media Intelligence Platform - Short Write-up

## Design and tradeoffs

I built a staged, auditable pipeline: heterogeneous JSON/CSV -> Pydantic cleaning -> patient-level FHIR R4 Bundles -> SQLite -> cached AI summaries -> MiniLM/FAISS -> FastAPI/Tailwind UI. The reproducible corpus contains 62 raw synthetic records and deliberately exercises missing fields, inconsistent dates and gender codes, duplicate content, and conflicting identifiers. Cleaning yields 60 unique records across 20 synthetic patients. Name + DOB reconciliation is understandable for a demo, but production identity matching would require a governed master patient index.

The FHIR layer creates Patient, Encounter, DocumentReference, and DiagnosticReport resources with resolvable subject/encounter references. Every Bundle is checked three ways: exact R4 4.0.1 models from `fhirclient`, Pydantic-v2 validation through the `fhir.resources` R4B overlap, and custom reference-integrity checks. Errors are stored with each Bundle, written to a JSON report, and exposed through the API/UI. The current corpus validates 20/20 Bundles.

For summarization, an OpenAI-compatible client calls DeepSeek with deterministic, non-thinking JSON output. The prompt permits only source-stated facts, forbids inferred diagnoses, requires chief concern/diagnoses/media/anomalies, and defines confidence as source completeness. Code enforces a 200-word clinical-field ceiling, adds an immutable disclaimer, records the model/generation method, retries empty JSON once, logs failures, and uses a low-confidence extractive fallback. Summaries are cached by patient plus versioned Bundle hash. The current run produced 20/20 LLM summaries; the longest was 76 words.

Search embeds record text and AI narrative with `all-MiniLM-L6-v2`, uses normalized vectors and FAISS inner-product ranking, and applies resource/date filters before ranking so narrow filters still receive the true top five. A deterministic hashing embedder is limited to tests/offline fallback. The reproducible 50-record benchmark measured roughly 0.006 seconds on the development machine, excluding one-time model startup.

## FHIR/clinical research and AI validation

I reviewed R4 Patient identity, DocumentReference attachment/context, DiagnosticReport conclusion/effective time, Encounter linkage, collection Bundles, and the distinction between schema validity and reference resolution. Summary quality checks currently cover required fields, source-only prompting, structured parsing/retry, total word budget, confidence/disclaimer presence, cache behavior, and visible source records. A production evaluation should add clinician-reviewed synthetic gold summaries and score factual consistency, critical omission, hallucination, anomaly recall, and claim-level provenance.

## With more time

I would add US Core profile and terminology-server validation, OCR/PDF ingestion, provenance links per summary claim, authentication/RBAC/encryption/audit controls, incremental background indexing, hybrid BM25/vector retrieval with reranking, monitoring, containerization, and a clinician-reviewed evaluation dashboard.
