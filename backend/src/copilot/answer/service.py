"""
One question, end to end: redact, retrieve under the user's rights, route to a model allowed to
see the evidence, answer, note when the rule has changed since, and append the exchange to the
audit chain. The chain links every record to the previous one by hash, so an edited or deleted
record is visible (verify_chain).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from time import perf_counter
from typing import Any

from psycopg.types.json import Jsonb

from ..config import ModelSpec, RetrievalConfig
from ..db import Conn, Principal
from ..retrieval.search import Candidate, retrieve
from ..text import Embedder, Vocabulary
from .answerers import Answer, Answerer, route
from .redact import redact


@dataclass
class Result:
    query_id: int
    outcome: str
    answer: str
    citations: list[dict[str, Any]]
    newer: dict[str, Any] | None
    model: str
    as_of: date
    trace: dict[str, Any]


def _record_hash(record: dict[str, Any], prev: str) -> str:
    payload = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(f"{prev}|{payload}".encode()).hexdigest()


def newer_version(conn: Conn, cited: Candidate, as_of: date) -> dict[str, Any] | None:
    """If the cited rule reads differently today, the current wording (the user may read it: same
    document, same rights)."""
    if cited.valid_to is None:
        return None
    row = conn.execute(
        """SELECT p.version, p.valid_from, p.text FROM paragraphs p
            WHERE p.doc_key = %s AND p.tz = %s AND p.valid_to IS NULL AND p.version > %s""",
        (cited.doc_key, cited.tz, cited.version),
    ).fetchone()
    if not row or row["text"] == cited.text:
        return None
    return {"version": row["version"], "valid_from": row["valid_from"].isoformat(), "text": row["text"]}


def ask(
    conn: Conn,
    who: Principal,
    question: str,
    as_of: date,
    *,
    cfg: RetrievalConfig,
    embedder: Embedder,
    thesaurus: dict[str, str],
    specs: tuple[ModelSpec, ...],
    answerers: dict[str, Answerer],
    vocab: Vocabulary | None = None,
) -> Result:
    t0 = perf_counter()
    clean, redacted = redact(question)
    r = retrieve(conn, clean, as_of, cfg, embedder, thesaurus, vocab)
    spec, why = route(specs, r.candidates)
    t1 = perf_counter()
    a: Answer = answerers[spec.id].answer(r, r.candidates)
    answer_ms = (perf_counter() - t1) * 1000
    newer = newer_version(conn, a.citations[0], as_of) if a.citations else None
    cost = (a.tokens_in * spec.price_in + a.tokens_out * spec.price_out) / 1_000_000
    trace: dict[str, Any] = {
        "timings_ms": {**{k: round(v, 2) for k, v in r.timings_ms.items()}, "answer": round(answer_ms, 2)},
        "total_ms": round((perf_counter() - t0) * 1000, 2),
        "redacted": redacted,
        "expanded_question": r.expanded,
        "asked": sorted(r.asked) if r.asked else None,
        "router": {"model": spec.id, "processing": spec.processing, "reason": why},
        "tokens": {"input": a.tokens_in, "output": a.tokens_out},
        "cost_eur": round(cost, 6),
        "notes": a.notes,
        "candidates": [
            {
                "paragraph_id": c.id,
                "doc_key": c.doc_key,
                "version": c.version,
                "tz": c.tz,
                "fts_rank": c.fts_rank,
                "vec_rank": c.vec_rank,
                "coverage": round(c.coverage, 3),
                "score": round(c.score, 4),
                "history": c.is_history,
                "answers_kind": r.answers_kind(c),
                "anchored": c.anchored,
            }
            for c in r.candidates
        ],
    }
    record = {
        "login": who.login,
        "question": clean,
        "as_of": as_of.isoformat(),
        "outcome": a.outcome,
        "answer": a.text,
        "model": a.model,
        "evidence": [c.id for c in r.candidates],
        "citations": [c.id for c in a.citations],
    }
    # One writer at a time extends the chain.
    conn.execute("SELECT pg_advisory_xact_lock(777001)")
    prev = conn.execute("SELECT last_query_hash() AS h").fetchone()["h"]  # type: ignore[index]
    digest = _record_hash(record, prev)
    row = conn.execute(
        """INSERT INTO queries (login, question, as_of, outcome, answer, model, evidence, citations, trace,
                                prev_hash, hash)
           VALUES (%(login)s, %(question)s, %(as_of)s, %(outcome)s, %(answer)s, %(model)s, %(evidence)s,
                   %(citations)s, %(trace)s, %(prev)s, %(hash)s) RETURNING id""",
        {**record, "trace": Jsonb(trace), "prev": prev, "hash": digest},
    ).fetchone()
    assert row is not None
    return Result(row["id"], a.outcome, a.text, [c.citation() for c in a.citations], newer, a.model, as_of, trace)


def verify_chain(conn: Conn) -> dict[str, Any]:
    """Recomputes every hash; returns the first broken link, if any. Run as an auditor or system."""
    prev = "genesis"
    n = 0
    for row in conn.execute(
        "SELECT id, login, question, as_of, outcome, answer, model, evidence, citations, prev_hash, hash"
        " FROM queries ORDER BY id"
    ):
        record = {
            "login": row["login"],
            "question": row["question"],
            "as_of": row["as_of"].isoformat(),
            "outcome": row["outcome"],
            "answer": row["answer"],
            "model": row["model"],
            "evidence": list(row["evidence"]),
            "citations": list(row["citations"]),
        }
        if row["prev_hash"] != prev or _record_hash(record, prev) != row["hash"]:
            return {"ok": False, "records": n, "broken_at": row["id"]}
        prev = row["hash"]
        n += 1
    return {"ok": True, "records": n, "broken_at": None}
