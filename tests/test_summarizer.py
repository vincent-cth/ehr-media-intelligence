import sys
from types import SimpleNamespace

import app.summarizer as summarizer
from app.fhir_mapper import build_bundles
from app.ingestion import clean_records
from app.storage import SQLiteStore


def sample_bundle():
    records = clean_records([
        {
            "id": "lab-1",
            "patient_name": "Avery Demo",
            "mrn": "123",
            "date": "2026-01-01",
            "type": "lab result",
            "title": "Metabolic panel",
            "text": "Chief concern: fatigue. Creatinine 1.4 mg/dL, flagged high.",
        }
    ])
    return next(iter(build_bundles(records).values()))


def test_fallback_summary_is_cached_disclaimed_and_under_200_words(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    store = SQLiteStore(tmp_path / "ehr.db")
    bundle = sample_bundle()
    first = summarizer.summarize_bundle("00000123", bundle, store)
    assert first.generation_method == "extractive_fallback"
    assert first.confidence == "low"
    assert "not a clinical decision" in first.disclaimer
    assert summarizer.clinical_word_count(first) <= 200

    monkeypatch.setattr(
        summarizer,
        "_extractive_fallback",
        lambda *_: (_ for _ in ()).throw(AssertionError("cache was not used")),
    )
    second = summarizer.summarize_bundle("00000123", bundle, store)
    assert second == first


def test_llm_summary_records_generation_method(tmp_path, monkeypatch):
    payload = {
        "chief_concern": "Fatigue",
        "key_diagnoses": [],
        "recent_media_records": ["Metabolic panel"],
        "flagged_anomalies": ["Creatinine reported high"],
        "narrative": "The source record documents fatigue and a flagged creatinine result.",
        "confidence": "high",
    }

    class FakeCompletions:
        def create(self, **_):
            message = SimpleNamespace(content=__import__("json").dumps(payload))
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeOpenAI:
        def __init__(self, **_):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    summary = summarizer.summarize_bundle(
        "00000123", sample_bundle(), SQLiteStore(tmp_path / "ehr.db"), force=True
    )
    assert summary.generation_method == "llm"
    assert summary.model == summarizer.settings.openai_model
    assert summarizer.clinical_word_count(summary) <= 200


def test_llm_empty_json_is_retried(tmp_path, monkeypatch):
    complete = {
        "chief_concern": "Fatigue", "key_diagnoses": [],
        "recent_media_records": ["Panel"], "flagged_anomalies": [],
        "narrative": "Fatigue documented.", "confidence": "medium",
    }

    class RetryingCompletions:
        calls = 0

        def create(self, **_):
            self.calls += 1
            content = "{}" if self.calls == 1 else __import__("json").dumps(complete)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    completions = RetryingCompletions()

    class FakeOpenAI:
        def __init__(self, **_):
            self.chat = SimpleNamespace(completions=completions)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    result = summarizer.summarize_bundle(
        "00000123", sample_bundle(), SQLiteStore(tmp_path / "retry.db"), force=True
    )
    assert completions.calls == 2
    assert result.generation_method == "llm"
