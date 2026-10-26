"""
Turning evidence into an answer.

Two answerers share one contract: given the question and the evidence paragraphs (already
permission- and date-filtered), return an answer that cites paragraphs, or decline. The
extractive answerer quotes the best paragraph and invents nothing; it runs in process and may see
every classification. The language-model answerer writes a short answer from the evidence; every
answer it gives is checked (verify) before anyone sees it, and a failed check falls back to the
extractive answer.

Which model may see the evidence is decided by the router from the model registry
(config/models.yaml): the most sensitive paragraph decides.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from ..config import ModelSpec, RetrievalConfig
from ..retrieval.search import Candidate, Retrieval
from ..text import numbers
from .answerability import AnswerabilityModel, features

NO_ANSWER = (
    "Dazu finde ich in den Richtlinien, die Sie einsehen dürfen und die zum gewählten Datum galten, "
    "keine Regelung. Bitte wenden Sie sich an den verantwortlichen Bereich."
)


@dataclass
class Answer:
    outcome: str  # answered | no_answer
    text: str
    citations: list[Candidate]
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    notes: list[str] = field(default_factory=list)


class Answerer(Protocol):
    spec: ModelSpec

    def answer(self, r: Retrieval, evidence: list[Candidate]) -> Answer: ...


def route(specs: tuple[ModelSpec, ...], evidence: list[Candidate]) -> tuple[ModelSpec, str]:
    """The first enabled model allowed to see every evidence paragraph, and why."""
    needed = max((c.classification for c in evidence), default=1)
    for spec in specs:
        if spec.enabled and spec.max_classification >= needed:
            return (
                spec,
                f"Belege bis Einstufung {needed}; {spec.id} darf bis Einstufung {spec.max_classification} sehen",
            )
    raise RuntimeError("no model may see this evidence; config/models.yaml needs an in-process answerer")


class Extractive:
    def __init__(self, spec: ModelSpec, cfg: RetrievalConfig, model: AnswerabilityModel | None = None) -> None:
        self.spec = spec
        self.cfg = cfg
        self.model = model

    def choose(self, r: Retrieval, evidence: list[Candidate]) -> tuple[Candidate | None, float | None]:
        """The paragraph to answer from (or None), and the model's probability for it."""
        usable = [c for c in evidence if r.change_intent or not c.is_history]
        if self.model is None or not usable:
            return (self._rules(r, usable), None)
        scored = sorted(((self.model.probability(features(r, c)), c) for c in usable), key=lambda t: (-t[0], t[1].id))
        p, best = scored[0]
        return (best if p >= self.model.threshold else None, p)

    def _rules(self, r: Retrieval, usable: list[Candidate]) -> Candidate | None:
        ok = [c for c in usable if r.answers_kind(c) and c.anchored and c.coverage >= self.cfg.min_overlap]
        return ok[0] if ok else None

    def answer(self, r: Retrieval, evidence: list[Candidate]) -> Answer:
        best, p = self.choose(r, evidence)
        if best is None:
            a = Answer("no_answer", NO_ANSWER, [], self.spec.id)
        else:
            text = f"{best.text} ({best.title}, Tz. {best.tz}, Version {best.version}, gültig ab {best.valid_from:%d.%m.%Y})"
            a = Answer("answered", text, [best], self.spec.id)
        if p is not None and self.model is not None:
            a.notes.append(
                f"Antwortbarkeit {p:.2f} (Schwelle {self.model.threshold:.2f}, Modell {self.model.version})".replace(
                    ".", ","
                )
            )
        return a


SYSTEM_PROMPT = """Du beantwortest Fragen von Mitarbeitenden der Havelsee Bank AG zu internen Richtlinien.
Antworte nur aus den nummerierten Absätzen unten, auf Deutsch, in höchstens drei Sätzen.
Nenne Beträge, Fristen und Zuständigkeiten genau so, wie sie im Absatz stehen.
Absätze aus einer Änderungshistorie nennen alte und neue Werte; für die geltende Regel zählt der Absatz der Regel selbst.
Wenn die Absätze die Frage nicht beantworten, antworte nicht und setze "answerable" auf false.
Antworte ausschließlich mit JSON: {"answerable": true|false, "answer": "...", "cited": [Absatznummern]}"""


def build_prompt(r: Retrieval, evidence: list[Candidate]) -> str:
    lines = [f"Stichtag: {r.as_of:%d.%m.%Y}", f"Frage: {r.question}", "", "Absätze:"]
    for i, c in enumerate(evidence, start=1):
        kind = " (Änderungshistorie)" if c.is_history else ""
        lines.append(f"[{i}] {c.title}, Tz. {c.tz}{kind}: {c.text}")
    return "\n".join(lines)


def verify(answer_text: str, cited: list[Candidate]) -> str | None:
    """Every number in the answer must appear in a cited paragraph. Returns the problem, if any."""
    if not cited:
        return "keine Fundstelle"
    available = set().union(*(numbers(c.text) for c in cited))
    unsupported = numbers(answer_text) - available
    if unsupported:
        return f"Zahlen nicht im zitierten Absatz: {', '.join(sorted(unsupported))}"
    return None


class Anthropic:
    """Claude through the Messages API. The transport is injectable for tests."""

    def __init__(
        self, spec: ModelSpec, fallback: Extractive, client: httpx.Client | None = None, timeout: float = 20.0
    ) -> None:
        self.spec = spec
        self.fallback = fallback
        self.client = client or httpx.Client(
            base_url=os.environ.get("COPILOT_ANTHROPIC_BASE_URL", "https://api.anthropic.com"), timeout=timeout
        )

    def _call(self, prompt: str) -> tuple[str, int, int]:
        res = self.client.post(
            "/v1/messages",
            headers={
                "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.spec.model,
                "max_tokens": 400,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        res.raise_for_status()
        body: dict[str, Any] = res.json()
        text = "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")
        usage = body.get("usage", {})
        return text, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))

    def answer(self, r: Retrieval, evidence: list[Candidate]) -> Answer:
        if not evidence:
            return Answer("no_answer", NO_ANSWER, [], self.spec.id)
        try:
            raw, tin, tout = self._call(build_prompt(r, evidence))
            match = re.search(r"\{.*\}", raw, re.S)
            data = json.loads(match.group(0) if match else raw)
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as e:
            a = self.fallback.answer(r, evidence)
            a.notes.append(f"{self.spec.id} nicht erreichbar ({type(e).__name__}); Absatz zitiert")
            return a
        if not data.get("answerable"):
            return Answer("no_answer", NO_ANSWER, [], self.spec.id, tin, tout)
        cited = [evidence[i - 1] for i in data.get("cited", []) if isinstance(i, int) and 1 <= i <= len(evidence)]
        text = str(data.get("answer", "")).strip()
        problem = verify(text, cited)
        if problem:
            a = self.fallback.answer(r, evidence)
            a.tokens_in, a.tokens_out = tin, tout
            a.notes.append(f"Antwort von {self.spec.id} verworfen: {problem}; Absatz zitiert")
            return a
        return Answer("answered", text, cited, self.spec.id, tin, tout)


def build_answerers(
    specs: tuple[ModelSpec, ...], cfg: RetrievalConfig, model: AnswerabilityModel | None = None
) -> dict[str, Answerer]:
    extractive_spec = next(s for s in specs if s.provider == "extractive")
    extractive = Extractive(extractive_spec, cfg, model)
    out: dict[str, Answerer] = {extractive_spec.id: extractive}
    for s in specs:
        if s.provider == "anthropic":
            out[s.id] = Anthropic(s, extractive)
    return out
