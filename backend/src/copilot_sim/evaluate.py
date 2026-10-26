"""
Measures the copilot against the simulated bank's truth.

For every question: is the right value in the answer, is the right paragraph of the right version
cited, was the right paragraph among the evidence (retrieval recall), did the copilot decline
when it should, and did a value the asker may not read ever appear in an answer, a citation or
the evidence (a leak). Two sets: `dev` (generated from the truth, used while building) and `blind`
(blind/questions.json, written from the documents alone by someone who never saw the code). The
first blind run is kept in reports/blind/FIRST_RUN.json and never rewritten.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from psycopg_pool import ConnectionPool

from copilot.answer.answerability import AnswerabilityModel
from copilot.answer.answerers import build_answerers
from copilot.answer.service import ask
from copilot.config import models, retrieval_config, settings, thesaurus
from copilot.db import as_system, as_user, principal
from copilot.retrieval.search import load_vocabulary
from copilot.text import SketchEmbedder

from .questions import as_dicts, dev_questions
from .world import World

SETS = {
    "blind": Path(__file__).parent / "blind" / "questions.json",
    # The first blind set: its failures were studied, so it is a regression set now.
    "regression-v1": Path(__file__).parent / "regression" / "blind-v1" / "questions.json",
}


def norm(s: str) -> str:
    return " ".join(s.lower().split())


@dataclass
class Outcome:
    id: str
    kind: str
    user: str
    question: str
    expect: str
    outcome: str
    correct: bool
    cited_right: bool | None
    in_evidence: bool | None
    leaked: bool
    ms: float
    answer: str
    cited: str | None


def run_set(pool: ConnectionPool, questions: list[dict[str, Any]]) -> list[Outcome]:
    cfg = retrieval_config()
    specs = models()
    answerers = build_answerers(specs, cfg, AnswerabilityModel.load(settings().config_dir / "answerability.json"))
    embedder = SketchEmbedder(cfg.embedding_dim)
    th = thesaurus()
    out: list[Outcome] = []
    with as_system(pool) as conn:
        vocab = load_vocabulary(conn, cfg.unknown_word_weight)
        para = {r["id"]: r for r in conn.execute("SELECT id, doc_key, version, tz, text FROM paragraphs").fetchall()}
    for q in questions:
        who = principal(pool, q["user"])
        if who is None:
            raise ValueError(f"unknown user {q['user']}")
        with as_user(pool, who, rollback=True) as conn:
            r = ask(
                conn,
                who,
                q["question"],
                date.fromisoformat(q["as_of"]),
                cfg=cfg,
                embedder=embedder,
                thesaurus=th,
                specs=specs,
                answerers=answerers,
                vocab=vocab,
            )
        evidence = [para[c["paragraph_id"]] for c in r.trace["candidates"]]
        cited = r.citations[0] if r.citations else None
        target = (q.get("doc_no"), q.get("version"), q.get("tz"))
        cited_right = in_evidence = None
        if q["expect"] == "answer":
            cited_right = bool(cited) and (cited["doc_key"], cited["version"], cited["tz"]) == target
            in_evidence = any((e["doc_key"], e["version"], e["tz"]) == target for e in evidence)
            correct = r.outcome == "answered" and norm(q["value"]) in norm(r.answer) and cited_right
        else:
            correct = r.outcome == "no_answer"
        leaked = False
        if q["kind"] == "no_access":
            # Nothing from the document the asker may not read may reach them in any form.
            leaked = any(e["doc_key"] == q["doc_no"] for e in evidence) or (
                bool(cited) and cited["doc_key"] == q["doc_no"]
            )
            if q.get("value") and norm(q["value"]) in norm(r.answer):
                # The same value may legitimately come from a document the user can read.
                leaked = leaked or (bool(cited) and cited["doc_key"] == q["doc_no"])
        out.append(
            Outcome(
                q["id"],
                q["kind"],
                q["user"],
                q["question"],
                q["expect"],
                r.outcome,
                bool(correct),
                cited_right,
                in_evidence,
                leaked,
                r.trace["total_ms"],
                r.answer,
                f"{cited['doc_key']} v{cited['version']} Tz. {cited['tz']}" if cited else None,
            )
        )
    return out


def summarise(rows: list[Outcome]) -> dict[str, Any]:
    ans = [r for r in rows if r.expect == "answer"]
    no = [r for r in rows if r.expect == "no_answer"]
    answered = [r for r in rows if r.outcome == "answered"]
    by_kind: dict[str, dict[str, Any]] = {}
    groups: dict[str, list[Outcome]] = defaultdict(list)
    for r in rows:
        groups[r.kind].append(r)
    for k, g in sorted(groups.items()):
        by_kind[k] = {
            "questions": len(g),
            "correct": sum(r.correct for r in g),
            "accuracy": _share([r.correct for r in g]),
        }
    ms = sorted(r.ms for r in rows)
    return {
        "questions": len(rows),
        "accuracy": _share([r.correct for r in rows]),
        "answer_accuracy": _share([r.correct for r in ans]),
        "retrieval_recall": _share([bool(r.in_evidence) for r in ans]),
        "declined_correctly": _share([r.correct for r in no]),
        # Of the answers given, how many were right (wrong answers are worse than no answer).
        "answer_precision": _share(
            [r.correct for r in answered if r.expect == "answer"] + [False for r in answered if r.expect == "no_answer"]
        ),
        "wrong_answers": sum(1 for r in answered if not r.correct),
        "leaks": sum(r.leaked for r in rows),
        "latency_ms_p50": round(statistics.median(ms), 1) if ms else None,
        "latency_ms_p95": round(ms[int(0.95 * (len(ms) - 1))], 1) if ms else None,
        "by_kind": by_kind,
    }


def _share(xs: list[bool]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def _record_first_run(first: Path, results: dict[str, Any], failures: list[dict[str, Any]]) -> None:
    """The first run of a blind set is kept as it was; later runs never overwrite it."""
    if first.exists():
        return
    first.parent.mkdir(parents=True, exist_ok=True)
    payload = {"recorded_at": results["generated_at"], "summary": results["sets"]["blind"], "failures": failures}
    first.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def evaluate(
    pool: ConnectionPool, reports: Path, sets: tuple[str, ...] = ("dev", "regression-v1", "blind")
) -> dict[str, Any]:
    world = World()
    from .render import layout

    for p in world.policies:  # fills paragraph numbers into world.tz
        layout(world, p, 1)
    results: dict[str, Any] = {"generated_at": datetime.now(UTC).isoformat(), "sets": {}}
    failures: dict[str, list[dict[str, Any]]] = {}
    for name in sets:
        qs = as_dicts(dev_questions(world)) if name == "dev" else json.loads(SETS[name].read_text(encoding="utf-8"))
        rows = run_set(pool, qs)
        results["sets"][name] = summarise(rows)
        failures[name] = [r.__dict__ for r in rows if not r.correct or r.leaked]
        counts = Counter(r.kind for r in rows)
        results["sets"][name]["kinds"] = dict(counts)
    reports.mkdir(parents=True, exist_ok=True)
    if "blind" in results["sets"]:
        _record_first_run(reports / "blind" / "FIRST_RUN.json", results, failures["blind"])
    results["first_runs"] = {
        name: json.loads(path.read_text(encoding="utf-8"))["summary"]
        for name, path in (
            ("blind", reports / "blind" / "FIRST_RUN.json"),
            ("regression-v1", reports / "regression" / "blind-v1" / "FIRST_RUN.json"),
        )
        if path.exists()
    }
    (reports / "evaluation.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name in ("dev", "regression-v1"):
        if name in failures:
            (reports / f"failures_{name}.json").write_text(
                json.dumps(failures[name], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
    return results
