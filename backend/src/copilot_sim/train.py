"""
Trains the answerability model (copilot/answer/answerability.py) on labelled questions: the dev
questions and the regression set (the first blind set, whose failures were studied). The current
blind set is never used here; it measures the trained model once.

Each evidence paragraph of each question is a row, labelled 1 if it is the paragraph that answers
the question. Out-of-fold probabilities (questions grouped, so a question's paragraphs never sit
on both sides) pick the threshold: the lowest one at which wrong answers stay within
`max_wrong_rate` of all questions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
from psycopg_pool import ConnectionPool
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

from copilot.answer.answerability import FEATURES, features
from copilot.config import retrieval_config, thesaurus
from copilot.db import as_system, as_user, principal
from copilot.retrieval.search import load_vocabulary, retrieve
from copilot.text import SketchEmbedder

from .evaluate import SETS
from .questions import as_dicts, dev_questions
from .render import layout
from .world import World


def rows_for(pool: ConnectionPool, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cfg = retrieval_config()
    emb = SketchEmbedder(cfg.embedding_dim)
    th = thesaurus()
    with as_system(pool) as conn:
        vocab = load_vocabulary(conn, cfg.unknown_word_weight)
    out = []
    for qi, q in enumerate(questions):
        who = principal(pool, q["user"])
        assert who is not None
        with as_user(pool, who) as conn:
            r = retrieve(conn, q["question"], date.fromisoformat(q["as_of"]), cfg, emb, th, vocab)
        target = (q.get("doc_no"), q.get("version"), q.get("tz")) if q["expect"] == "answer" else None
        for c in r.candidates:
            if c.is_history and not r.change_intent:
                continue
            out.append(
                {
                    "q": qi,
                    "x": features(r, c),
                    "y": int(target == (c.doc_key, c.version, c.tz)),
                    "answerable": q["expect"] == "answer",
                }
            )
        if not r.candidates:
            out.append({"q": qi, "x": None, "y": 0, "answerable": q["expect"] == "answer"})
    return out


def outcomes(rows: list[dict[str, Any]], p: np.ndarray, threshold: float, n_questions: int) -> dict[str, float]:
    """Per question: the best paragraph is used if its probability clears the threshold."""
    best: dict[int, tuple[float, int]] = {}
    for row, prob in zip(rows, p, strict=True):
        if row["x"] is None:
            continue
        if row["q"] not in best or prob > best[row["q"]][0]:
            best[row["q"]] = (float(prob), row["y"])
    correct = wrong = 0
    for prob, y in best.values():
        if prob >= threshold:
            if y:
                correct += 1
            else:
                wrong += 1
    return {"correct_answers": correct / n_questions, "wrong_answers": wrong / n_questions}


def train(
    pool: ConnectionPool,
    config_dir: Path,
    sets: tuple[str, ...] = ("dev", "regression-v1"),
    max_wrong_rate: float = 0.02,
) -> dict[str, Any]:
    world = World()
    for p in world.policies:
        layout(world, p, 1)
    questions: list[dict[str, Any]] = []
    for name in sets:
        qs = as_dicts(dev_questions(world)) if name == "dev" else json.loads(SETS[name].read_text(encoding="utf-8"))
        questions += qs
    rows = rows_for(pool, questions)
    data = [r for r in rows if r["x"] is not None]
    X = np.array([r["x"] for r in data], dtype=float)
    y = np.array([r["y"] for r in data])
    groups = np.array([r["q"] for r in data])
    mean, scale = X.mean(axis=0), X.std(axis=0)
    scale[scale == 0] = 1.0
    Xs = (X - mean) / scale

    oof = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(Xs, y, groups):
        m = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(Xs[tr], y[tr])
        oof[te] = m.predict_proba(Xs[te])[:, 1]
    grid = [round(t, 3) for t in np.linspace(0.05, 0.95, 91)]
    stats = {t: outcomes(data, oof, t, len(questions)) for t in grid}
    allowed = [t for t in grid if stats[t]["wrong_answers"] <= max_wrong_rate]
    threshold = min(allowed) if allowed else grid[-1]

    model = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(Xs, y)
    payload = {
        "features": list(FEATURES),
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "coef": model.coef_[0].tolist(),
        "intercept": float(model.intercept_[0]),
        "threshold": threshold,
        "trained_on": {name: sum(1 for _ in [0]) for name in sets} | {"questions": len(questions), "rows": len(y)},
        "cross_validation": {"threshold": threshold, **stats[threshold], "max_wrong_rate": max_wrong_rate},
        "trained_at": datetime.now(UTC).isoformat(),
    }
    payload["trained_on"] = {"sets": list(sets), "questions": len(questions), "rows": len(y)}
    payload["version"] = hashlib.sha256(json.dumps(payload["coef"]).encode()).hexdigest()[:10]
    (config_dir / "answerability.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
