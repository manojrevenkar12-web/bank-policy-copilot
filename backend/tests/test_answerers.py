import json
from datetime import date

import httpx

from copilot.answer.answerers import Anthropic, Extractive, route, verify
from copilot.config import ModelSpec, retrieval_config
from copilot.retrieval.search import Candidate, Retrieval

SPECS = (
    ModelSpec("claude", "anthropic", "m", 2, "external", 3.0, 15.0, None),
    ModelSpec("extractive", "extractive", "x", 4, "in process", 0.0, 0.0, None),
)


def cand(id: int, text: str, level: int = 2, **kw: object) -> Candidate:
    c = Candidate(id, "RL-ZV-01", "Richtlinie", 2, f"2.{id}", "Freigabe", text, False, date(2024, 1, 1), None, level)
    c.coverage, c.anchored = 0.8, True
    c.types = frozenset({"amount"})
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def retrieval(*cs: Candidate) -> Retrieval:
    return Retrieval(
        "Ab welchem Betrag?", "Ab welchem Betrag?", date(2025, 1, 1), list(cs), {}, False, frozenset({"amount"})
    )


def test_the_most_sensitive_paragraph_decides_the_model() -> None:
    assert route(SPECS, [cand(1, "a", 2)])[0].id == "claude"
    assert route(SPECS, [cand(1, "a", 2), cand(2, "b", 3)])[0].id == "extractive"


def test_verify_rejects_numbers_not_in_the_cited_paragraph() -> None:
    c = cand(1, "Zahlungen ab 15.000 EUR brauchen zwei Freigaben.")
    assert verify("Ab 15.000 EUR.", [c]) is None
    assert "20000" in (verify("Ab 20.000 EUR.", [c]) or "")
    assert verify("Ab 15.000 EUR.", []) == "keine Fundstelle"


def fake_claude(payload: dict[str, object] | Exception) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(payload, Exception):
            raise payload
        body = {
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "usage": {"input_tokens": 120, "output_tokens": 30},
        }
        return httpx.Response(200, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://claude.test")


def test_claude_answer_is_used_when_it_checks_out() -> None:
    ext = Extractive(SPECS[1], retrieval_config())
    c = cand(1, "Zahlungen ab 15.000 EUR brauchen zwei Freigaben.")
    a = Anthropic(SPECS[0], ext, fake_claude({"answerable": True, "answer": "Ab 15.000 EUR.", "cited": [1]})).answer(
        retrieval(c), [c]
    )
    assert (a.outcome, a.model, a.text, a.tokens_in) == ("answered", "claude", "Ab 15.000 EUR.", 120)


def test_an_invented_number_falls_back_to_the_quote() -> None:
    ext = Extractive(SPECS[1], retrieval_config())
    c = cand(1, "Zahlungen ab 15.000 EUR brauchen zwei Freigaben.")
    a = Anthropic(SPECS[0], ext, fake_claude({"answerable": True, "answer": "Ab 20.000 EUR.", "cited": [1]})).answer(
        retrieval(c), [c]
    )
    assert a.model == "extractive" and "15.000 EUR" in a.text
    assert any("verworfen" in n for n in a.notes)


def test_model_declines_and_outages_are_handled() -> None:
    ext = Extractive(SPECS[1], retrieval_config())
    c = cand(1, "Zahlungen ab 15.000 EUR brauchen zwei Freigaben.")
    a = Anthropic(SPECS[0], ext, fake_claude({"answerable": False})).answer(retrieval(c), [c])
    assert a.outcome == "no_answer"
    a = Anthropic(SPECS[0], ext, fake_claude(httpx.ConnectError("down"))).answer(retrieval(c), [c])
    assert a.model == "extractive" and any("nicht erreichbar" in n for n in a.notes)


def test_extractive_rules_without_a_model() -> None:
    ext = Extractive(SPECS[1], retrieval_config())
    weak = cand(1, "Zahlungen ab 15.000 EUR.", coverage=0.1)
    assert ext.answer(retrieval(weak), [weak]).outcome == "no_answer"
    other_kind = cand(2, "Innerhalb von 2 Stunden.", types=frozenset({"duration"}))
    assert ext.answer(retrieval(other_kind), [other_kind]).outcome == "no_answer"
    history = cand(3, "Version 2: von 25.000 EUR auf 15.000 EUR.", is_history=True)
    good = cand(4, "Zahlungen ab 15.000 EUR brauchen zwei Freigaben.")
    a = ext.answer(retrieval(history, good), [history, good])
    assert a.citations[0].id == 4
