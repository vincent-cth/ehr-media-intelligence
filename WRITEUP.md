# EHR Media Intelligence Platform

AI Full-stack Internship Assessment | Python, FHIR R4, Clinical AI, Semantic Search

## 01 System design

I built an auditable pipeline from heterogeneous JSON and CSV through Pydantic cleaning, patient-level FHIR R4 Bundles, SQLite persistence, cached clinical summaries, MiniLM/FAISS search, and a FastAPI/Tailwind interface. The deterministic corpus starts with 62 synthetic raw records and exercises missing fields, inconsistent dates and gender codes, duplicate content, and conflicting identifiers. Cleaning produces 60 unique records across 20 patients.

## 02 FHIR R4 and auditability

The mapper creates Patient, Encounter, DocumentReference, and DiagnosticReport resources with resolvable subject and encounter references. Every Bundle is checked by exact R4 4.0.1 models from fhirclient, Pydantic validation through fhir.resources, and custom reference-integrity checks. Validation results are stored in SQLite, written to JSON, and surfaced through both the API and UI. Every normalization is retained as a per-record AuditEvent.

## 03 Clinical AI safety

An OpenAI-compatible client calls DeepSeek for six-field structured summaries. The prompt permits only source-stated facts, forbids inferred diagnoses, and requires reported anomalies to remain tied to their source. Code enforces a 200-word clinical limit, records confidence/model/generation method, adds a permanent non-clinical-decision disclaimer, retries empty JSON, logs failures, and provides a visibly low-confidence fallback. Caching uses patient ID plus a versioned Bundle hash.

## 04 Search and clinician UX

The system embeds record text and AI narratives with all-MiniLM-L6-v2 and ranks normalized vectors with FAISS. Resource type and date constraints are applied before ranking, preserving the true filtered top five. The responsive UI provides debounced search, ranked cards, AI and source snippets, filters, loading/error/empty states, patient detail, FHIR status, audit trails, ARIA live regions, and keyboard navigation.

## 05 Validation evidence

- 60 unique synthetic records across 20 patients
- 20 of 20 patient Bundles pass all validation layers
- 20 of 20 current summaries generated through the LLM path
- Longest current clinical summary is 76 words
- 15 automated tests pass; 50-record search is about 0.006 seconds

## 06 Tradeoffs and next steps

Name plus DOB reconciliation is transparent but not a production master patient index. FAISS is ideal at assessment scale, while production search should add lexical retrieval and reranking. Next steps are US Core profiles and terminology services, OCR/PDF ingestion, claim-level provenance, clinician-reviewed factuality and omission scoring, authentication/RBAC/encryption/audit controls, incremental background indexing, observability, and containerized deployment.
