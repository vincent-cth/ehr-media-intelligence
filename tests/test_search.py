from app.search import Embedder, SemanticIndex


def test_semantic_search_returns_ranked_filtered_hits():
    embedder = Embedder.__new__(Embedder)
    embedder.model_name = "offline"
    embedder.dimension = 128
    embedder._model = None
    index = SemanticIndex(embedder=embedder)
    index._faiss = None
    index._index = None
    index.build([
        {"record_id":"1","patient_id":"p1","patient_name":"A","resource_type":"DiagnosticReport","record_date":"2026-01-01","title":"Chest X-ray","text":"left basilar opacity on chest imaging"},
        {"record_id":"2","patient_id":"p2","patient_name":"B","resource_type":"DocumentReference","record_date":"2026-02-01","title":"Discharge","text":"ankle sprain improved"},
    ])
    hits = index.search("chest opacity", resource_type="DiagnosticReport")
    assert hits
    assert hits[0].record_id == "1"
    assert hits[0].resource_type == "DiagnosticReport"


def test_filters_are_applied_before_top_five_ranking():
    embedder = Embedder.__new__(Embedder)
    embedder.model_name = "offline"
    embedder.dimension = 128
    embedder._model = None
    index = SemanticIndex(embedder=embedder)
    index._faiss = None
    index._index = None
    rows = [
        {
            "record_id": str(i),
            "patient_id": f"p{i}",
            "patient_name": f"Patient {i}",
            "resource_type": "DocumentReference" if i < 50 else "DiagnosticReport",
            "record_date": "2025-01-01" if i < 50 else "2026-03-01",
            "title": "Chest imaging",
            "text": f"chest imaging opacity record {i}",
            "summary_snippet": f"AI summary for record {i}",
        }
        for i in range(55)
    ]
    index.build(rows)
    hits = index.search(
        "chest imaging opacity",
        resource_type="DiagnosticReport",
        date_from="2026-01-01",
        top_k=5,
    )
    assert len(hits) == 5
    assert all(hit.resource_type == "DiagnosticReport" for hit in hits)
    assert all(hit.record_date and hit.record_date >= "2026-01-01" for hit in hits)
    assert all(hit.snippet.startswith("AI summary") for hit in hits)
