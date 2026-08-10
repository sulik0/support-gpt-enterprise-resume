import json
from pathlib import Path

import pytest

from src.evaluation.offline_rag import (
    load_evaluation_dataset,
    run_offline_evaluation,
)
from src.llm.provider import MockLLMProvider
from src.observability.langsmith_tracing import sanitize_trace_value


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "evaluation" / "golden" / "support_qa_golden.json"


def test_golden_dataset_is_valid_and_unique():
    cases = load_evaluation_dataset(DATASET_PATH)

    assert len(cases) >= 10
    assert len({case.id for case in cases}) == len(cases)
    assert all(case.reference_answer for case in cases)
    assert all(case.expected_sources for case in cases)


def test_trace_sanitizer_redacts_secrets_and_pii():
    sanitized = sanitize_trace_value(
        {
            "message": "Contact alice@example.com or +86 138 0013 8000",
            "api_key": "secret-value",
        }
    )

    assert "alice@example.com" not in sanitized["message"]
    assert "138 0013 8000" not in sanitized["message"]
    assert sanitized["api_key"] == "[FILTERED]"


@pytest.mark.asyncio
async def test_traced_llm_method_preserves_provider_contract():
    provider = MockLLMProvider()

    result = await provider.analyze_ticket("I need a billing refund")

    assert result[0]["department"] == "billing"
    assert result[1:] == (150, 45)


@pytest.mark.asyncio
async def test_offline_evaluation_writes_json_and_markdown(tmp_path):
    async def fake_workflow(state):
        return {
            "suggested_response": (
                "Refund requests are allowed within 30 days when there is no active dispute."
            ),
            "context_citations": [
                {
                    "source": "Corporate Refund Policy (v1)",
                    "text": (
                        "Refund requests must be filed within 30 days and require no active disputes."
                    ),
                }
            ],
            "errors": [],
        }

    paths = await run_offline_evaluation(
        DATASET_PATH,
        tmp_path,
        engine="local",
        limit=1,
        workflow_runner=fake_workflow,
    )

    report = json.loads(paths["json"].read_text(encoding="utf-8"))
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert report["engine"] == "local"
    assert report["case_count"] == 1
    assert set(report["aggregates"]) == {
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    }
    assert report["cases"][0]["citation_hit"] is True
    assert "Agent Evaluation 评测报告" in markdown


@pytest.mark.asyncio
async def test_ragas_mode_requires_real_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    async def fake_workflow(state):
        return {"suggested_response": "answer", "context_citations": [], "errors": []}

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await run_offline_evaluation(
            DATASET_PATH,
            Path("unused"),
            engine="ragas",
            limit=1,
            workflow_runner=fake_workflow,
        )
