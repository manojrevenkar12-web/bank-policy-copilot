"""
Hybrid retrieval over the paragraphs a user may read that were in force on a date.

Two paths run in the database under the user's row-level security: German full-text search and
nearest neighbours on the sketch embedding. Their rankings are fused (reciprocal rank fusion) and
re-scored by how much of the question each paragraph covers. Change-history paragraphs, which
repeat old and new values, count less unless the question asks what changed.

Validity and permission are filters in the SQL, not afterthoughts: a paragraph that was not in
force on the date, or that the user may not read, never becomes a candidate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from time import perf_counter
from typing import Any

from ..config import RetrievalConfig
from ..db import Conn
from ..text import (
    Embedder,
    Vocabulary,
    apply_thesaurus,
    asked_types,
    overlap,
    stated_types,
    stems,
    tsquery_terms,
)

CHANGE_INTENT = re.compile(r"\b(geändert|geaendert|änderung|aenderung|vorher|bisher|früher|alt(e|en)? wert)", re.I)

VALID_ON = "valid_from <= %(on)s AND (valid_to IS NULL OR valid_to > %(on)s)"


@dataclass
class Candidate:
    id: int
    doc_key: str
    title: str
    version: int
    tz: str
    section: str
    text: str
    is_history: bool
    valid_from: date
    valid_to: date | None
    classification: int
    types: frozenset[str] = frozenset()
    anchored: bool = True  # the document contains the question's rarest known noun
    section_coverage: float = 0.0
    known_coverage: float = 0.0  # share of the question's known words found, unweighted
    rrf_rel: float = 0.0
    position: int = 0
    fts_rank: int | None = None
    vec_rank: int | None = None
    rrf: float = 0.0
    coverage: float = 0.0
    score: float = 0.0

    def citation(self) -> dict[str, Any]:
        return {
            "paragraph_id": self.id,
            "doc_key": self.doc_key,
            "title": self.title,
            "version": self.version,
            "tz": self.tz,
            "section": self.section,
            "text": self.text,
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "classification": self.classification,
        }


@dataclass
class Retrieval:
    question: str
    expanded: str
    as_of: date
    candidates: list[Candidate]
    timings_ms: dict[str, float]
    change_intent: bool
    asked: frozenset[str] | None = None
    unknown_share: float = 0.0  # share of question words no policy uses
    question_words: int = 0

    def answers_kind(self, c: Candidate) -> bool:
        """Does the paragraph state the kind of value asked for (an amount, a deadline, a role)?"""
        return self.asked is None or bool(self.asked & c.types)


def retrieve(
    conn: Conn,
    question: str,
    as_of: date,
    cfg: RetrievalConfig,
    embedder: Embedder,
    thesaurus: dict[str, str],
    vocab: Vocabulary | None = None,
) -> Retrieval:
    timings: dict[str, float] = {}
    t0 = perf_counter()
    expanded = apply_thesaurus(question, thesaurus)
    terms = tsquery_terms(expanded)
    qvec = embedder.embed([expanded])[0]
    timings["prepare"] = (perf_counter() - t0) * 1000

    ranks: dict[int, dict[str, int]] = {}
    t1 = perf_counter()
    if terms:
        rows = conn.execute(
            f"""SELECT id FROM paragraphs, to_tsquery('german', %(q)s) q
                 WHERE tsv @@ q AND {VALID_ON}
                 ORDER BY ts_rank_cd(tsv, q, 32) DESC, id LIMIT %(n)s""",
            {"q": terms, "on": as_of, "n": cfg.candidates_per_path},
        ).fetchall()
        for i, r in enumerate(rows, start=1):
            ranks.setdefault(r["id"], {})["fts"] = i
    timings["fulltext"] = (perf_counter() - t1) * 1000

    t2 = perf_counter()
    # The validity and permission filters shrink the result set; a wider search keeps HNSW recall.
    conn.execute("SET LOCAL hnsw.ef_search = 200")
    rows = conn.execute(
        f"""SELECT id FROM paragraphs WHERE {VALID_ON}
             ORDER BY embedding <=> %(v)s, id LIMIT %(n)s""",
        {"v": qvec, "on": as_of, "n": cfg.candidates_per_path},
    ).fetchall()
    for i, r in enumerate(rows, start=1):
        ranks.setdefault(r["id"], {})["vec"] = i
    timings["vector"] = (perf_counter() - t2) * 1000

    t3 = perf_counter()
    candidates: list[Candidate] = []
    if ranks:
        rows = conn.execute(
            """SELECT p.id, p.doc_key, d.title, p.version, p.tz, p.section, p.text, p.is_history,
                      p.valid_from, p.valid_to, p.classification
                 FROM paragraphs p JOIN documents d ON d.doc_key = p.doc_key
                WHERE p.id = ANY(%s)""",
            (list(ranks),),
        ).fetchall()
        qstems = stems(expanded)
        anchor = vocab.anchor(question) if vocab else None
        change = bool(CHANGE_INTENT.search(question))
        for r in rows:
            c = Candidate(**r)
            rk = ranks[c.id]
            c.fts_rank, c.vec_rank = rk.get("fts"), rk.get("vec")
            c.rrf = sum(1.0 / (cfg.rrf_k + v) for v in rk.values())
            body = stems(f"{c.title} {c.section} {c.text}")
            c.coverage = overlap(qstems, body, vocab)
            known = {q for q in qstems if vocab.known(q)} if vocab else qstems
            c.known_coverage = overlap(known, body) if known else 0.0
            c.types = stated_types(c.text)
            if anchor and vocab:
                # The question's topic word must be in the document (not necessarily this paragraph).
                c.anchored = vocab.in_document(anchor, c.doc_key, c.version)
            c.section_coverage = overlap(qstems, stems(c.section), vocab)
            c.score = c.coverage + cfg.section_boost * c.section_coverage
            candidates.append(c)
        top_rrf = max(c.rrf for c in candidates)
        for c in candidates:
            c.rrf_rel = c.rrf / top_rrf
            c.score += 0.5 * c.rrf_rel
            if c.is_history and not change:
                c.score *= cfg.history_penalty
        candidates.sort(key=lambda c: (-c.score, c.id))
    else:
        change = False
    timings["rerank"] = (perf_counter() - t3) * 1000
    asked = asked_types(question)
    if asked:
        # Paragraphs that state the kind of value asked for go first.
        candidates.sort(key=lambda c: (not (asked & c.types), -c.score, c.id))
    for i, c in enumerate(candidates):
        c.position = i
    qs = stems(question)
    unknown = sum(1 for q in qs if vocab and not vocab.known(q)) / len(qs) if qs else 0.0
    return Retrieval(question, expanded, as_of, candidates[: cfg.evidence], timings, change, asked, unknown, len(qs))


def load_vocabulary(conn: Conn, unknown_weight: float = 1.0) -> Vocabulary:
    """Stem frequencies and per-document stems over all paragraphs (run as the system; only
    counts and stem sets leave this function, and a document's stems are only consulted for
    documents the asker could already retrieve)."""
    rows = conn.execute(
        """SELECT p.doc_key, p.version, d.title, p.section || ' ' || p.text AS t
             FROM paragraphs p JOIN documents d ON d.doc_key = p.doc_key"""
    ).fetchall()
    docs: dict[tuple[str, int], str] = {}
    for r in rows:
        key = (r["doc_key"], r["version"])
        docs[key] = f"{docs.get(key, r['title'])} {r['t']}"
    return Vocabulary([r["t"] for r in rows], docs, unknown_weight)
