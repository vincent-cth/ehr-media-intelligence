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
