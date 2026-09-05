# EHR Media Intelligence Platform - Short Write-up

## Design and tradeoffs
I used a staged pipeline: heterogeneous JSON/CSV -> canonical Pydantic records with per-record audit events -> patient-level FHIR Bundles -> SQLite persistence -> AI summary cache -> semantic index -> FastAPI + Tailwind UI. Identity reconciliation uses normalized name + DOB as a conservative demo key and keeps the first normalized MRN, while logging later conflicts. This is intentionally simple and auditable; production master-patient-index logic would require stronger probabilistic matching and governance.

The demo corpus is generated deterministically and contains 62 raw synthetic records across JSON and CSV for 20 synthetic patients. Two records are deliberate duplicates, so cleaning yields 60 unique records. The corpus intentionally includes mixed date formats, missing and conflicting MRNs, inconsistent gender codes, a missing source identifier, labs, imaging, discharge notes, and scanned follow-ups. This provides enough records to exercise the search requirement without including any real patient data.

The FHIR layer creates Patient, Encounter, DocumentReference, and DiagnosticReport resources and checks reference integrity in addition to `fhir.resources` validation. Current `fhir.resources` exposes prior-release validation through its R4B namespace, so I restrict the generated fields to R4-compatible elements and would add the official HL7 R4 validator in production. Text documents are represented as base64 text/plain attachments. For search I chose all-MiniLM-L6-v2 + FAISS for low local latency. A deterministic hashing embedder is only an offline/test fallback so the project remains demonstrable without model downloads.

The OpenAI summarizer is temperature-0, JSON-constrained, under-200-word prompt engineered, and cached by patient ID + hash of the FHIR Bundle. If no API key is present, the UI uses a clearly lower-confidence extractive fallback rather than failing. This improves evaluator usability but the API path is the intended AI implementation.

## FHIR/clinical concepts researched
I focused on Patient identity, DocumentReference attachments, DiagnosticReport conclusions, Encounter linkage, Bundle collections, FHIR references, and conservative handling of clinical text. The application never interprets a summary as a diagnosis and labels all summary output as AI-generated.

## AI summary quality validation
For a production evaluation I would create a synthetic gold set reviewed by a clinician and score: factual consistency against source records, omission of critical findings, hallucination rate, coverage of chief concern/diagnoses/recent media/anomalies, and word-count compliance. Automated regression checks would assert that every generated claim can be traced to source text and that no summary exceeds the word budget. The current demo additionally uses deterministic temperature, structured JSON output, explicit non-invention instructions, and a source-linked detail view.

## With more time
I would add a real MPI strategy, terminology normalization (LOINC/SNOMED), FHIR server validation against the official R4 validator, OCR/PDF extraction, PHI-aware access controls and audit trails, background ingestion jobs, hybrid BM25 + vector retrieval, reranking, model-evaluation dashboards, observability, and containerized deployment with CI.
