"""Phase 3 metrics are deterministic and use labelled examples only."""
from types import SimpleNamespace

from src.evaluation.metrics import score_query, summarize_queries


def test_evidence_precision_and_unsupported_answer_metrics():
    q = {"kind": "evidence", "intent": "EVIDENCE", "question": "why?", "answer": "blue",
         "evidence_sessions": ["s1"]}
    answer = SimpleNamespace(found=True, value="blue", evidence=[
        {"session_id": "s1", "role": "current"}, {"session_id": "extra", "role": "current"},
    ])
    scored = score_query(q, answer)
    assert scored["correct"] and scored["evidence_recall"] == 1.0
    assert scored["evidence_precision"] == 0.5 and not scored["unsupported_answer"]
    wrong = dict(scored, correct=False, found=True, unsupported_answer=True)
    summary = summarize_queries([scored, wrong], with_ci=False)
    assert summary["unsupported_answer_rate"]["value"] == 0.5
    assert summary["unsupported_answer_rate"]["unsupported"] == 1
    assert summary["unsupported_answer_rate"]["denominator"] == 2


def test_correct_abstention_on_unanswerable_question():
    q = {"kind": "as_of", "intent": "AS_OF", "question": "before records?", "answer": None,
         "answerable": False, "evidence_sessions": []}
    answer = SimpleNamespace(found=False, value=None, evidence=[])
    scored = score_query(q, answer)
    assert scored["correct"] and not scored["unsupported_answer"]
