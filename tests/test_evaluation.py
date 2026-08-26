import pytest
from src.evaluation.hallucination import hallucination_evaluator
from src.evaluation.retrieval_metrics import retrieval_metrics_evaluator
from src.evaluation.response_metrics import response_metrics_evaluator
from src.evaluation.framework import run_deeval_evaluation
from src.evaluation.framework import _save_single_response_report

def test_hallucination_scorer():
    context = ["Corporate billing rules assert refunds are valid up to 30 days."]
    response_faithful = "According to corporate billing rules, refunds are valid for 30 days."
    response_hallucinated = "We refund all user payments up to 90 days and give a free coupon."
    
    faithful_rate = hallucination_evaluator.evaluate(context, response_faithful)
    hallucinated_rate = hallucination_evaluator.evaluate(context, response_hallucinated)
    
    assert faithful_rate < 0.2
    assert hallucinated_rate > 0.4

def test_retrieval_metrics():
    query = "configure account preferences email"
    context_relevant = ["To configure account settings, open Preferences and modify your email."]
    context_irrelevant = ["We offer delivery services via shipping carriers."]
    
    precision_rel = retrieval_metrics_evaluator.calculate_precision(query, context_relevant)
    precision_irrel = retrieval_metrics_evaluator.calculate_precision(query, context_irrelevant)
    
    assert precision_rel > 0.5
    assert precision_irrel == 0.0

def test_response_metrics():
    query = "billing refund invoice"
    response = "I can refund your billing invoice."
    
    relevance = response_metrics_evaluator.calculate_relevance(query, response)
    assert relevance > 0.5

@pytest.mark.asyncio
async def test_unified_evaluation_framework(tmp_path, monkeypatch):
    query = "api outage devops"
    context = ["API outages are resolved by DevOps."]
    response = "API outages are resolved by DevOps."
    
    report_dir = tmp_path / "single_response"
    monkeypatch.setattr("src.evaluation.framework.SINGLE_REPORT_DIR", report_dir)
    res = await run_deeval_evaluation(query, context, response)
    
    assert res.overall_quality_score >= 0.70
    assert res.passed_evaluation is True
    assert len(res.report_summary) > 0
    
    reports = list(report_dir.glob("single_response_*.json"))
    assert len(reports) == 1
    payload = __import__("json").loads(reports[0].read_text(encoding="utf-8"))
    assert payload["experiment_config"]["evaluator"] == "single_response_v1"


def test_single_response_reports_apply_retention(tmp_path, monkeypatch):
    report_dir = tmp_path / "single_response"
    monkeypatch.setattr("src.evaluation.framework.SINGLE_REPORT_DIR", report_dir)
    monkeypatch.setattr("src.evaluation.framework.SINGLE_REPORT_RETENTION", 2)

    for sequence in range(3):
        _save_single_response_report({"sequence": sequence})

    reports = sorted(report_dir.glob("single_response_*.json"))
    assert len(reports) == 2
