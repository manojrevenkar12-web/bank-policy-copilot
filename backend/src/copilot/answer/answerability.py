"""
Should the copilot answer, and from which paragraph? A logistic model over features of each
evidence paragraph (how much of the question it covers, whether it states the kind of value
asked for, its ranks in both retrieval paths, ...) estimates the probability that the paragraph
answers the question. The best paragraph is used if that probability clears the threshold;
otherwise the copilot declines.

The weights and threshold are trained offline on labelled questions (the simulation package's
train-answerability command) and stored in config/answerability.json. The threshold is chosen so that,
in cross-validation, wrong answers stay rare: a decline costs a colleague a phone call, a wrong
limit can cost money. Scoring is a dot product: no ML library at runtime.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from ..retrieval.search import Candidate, Retrieval

FEATURES = (
    "coverage",
    "known_coverage",
    "section_coverage",
    "anchored",
    "kind_matches",
    "asks_value",
    "fts_inv",
    "vec_inv",
    "rrf_rel",
    "position_inv",
    "unknown_share",
    "question_words",
)


def features(r: Retrieval, c: Candidate) -> list[float]:
    return [
        c.coverage,
        c.known_coverage,
        c.section_coverage,
        float(c.anchored),
        float(r.answers_kind(c)),
        float(r.asked is not None),
        1.0 / c.fts_rank if c.fts_rank else 0.0,
        1.0 / c.vec_rank if c.vec_rank else 0.0,
        c.rrf_rel,
        1.0 / (c.position + 1),
        r.unknown_share,
        min(r.question_words, 20) / 10.0,
    ]


@dataclass(frozen=True)
class AnswerabilityModel:
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    coef: tuple[float, ...]
    intercept: float
    threshold: float
    version: str

    @classmethod
    def load(cls, path: Path) -> AnswerabilityModel | None:
        if not path.exists():
            return None
        d = json.loads(path.read_text(encoding="utf-8"))
        if tuple(d["features"]) != FEATURES:
            raise ValueError(f"{path} was trained on other features; retrain it")
        return cls(
            tuple(d["mean"]),
            tuple(d["scale"]),
            tuple(d["coef"]),
            float(d["intercept"]),
            float(d["threshold"]),
            d["version"],
        )

    def probability(self, x: list[float]) -> float:
        z = self.intercept + sum(
            w * (v - m) / (s or 1.0) for w, v, m, s in zip(self.coef, x, self.mean, self.scale, strict=True)
        )
        return 1.0 / (1.0 + math.exp(-z))
