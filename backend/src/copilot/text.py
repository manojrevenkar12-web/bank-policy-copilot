"""
German text handling for questions and paragraphs: folding, content words, light stemming,
number extraction, a thesaurus for colloquial terms, and a local embedding.

The embedding is a signed feature-hashing sketch of character n-grams (3 to 5) and words,
projected to a fixed dimension. It needs no model download and no training, it is
deterministic, and character n-grams match German compounds and inflections ("Übernachtungskosten"
and "Übernachtung") that whole-word search misses. Production deployments can swap in a hosted
multilingual embedding behind the same interface (Embedder); the dimension is configured in
config/retrieval.yaml.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Protocol

import numpy as np
import snowballstemmer

STOPWORDS = frozenset(
    [
        "der",
        "die",
        "das",
        "den",
        "dem",
        "des",
        "ein",
        "eine",
        "einer",
        "eines",
        "einem",
        "einen",
        "und",
        "oder",
        "ist",
        "sind",
        "war",
        "wird",
        "werden",
        "wurde",
        "ab",
        "bis",
        "wie",
        "welche",
        "welcher",
        "welches",
        "welchen",
        "welchem",
        "wann",
        "wer",
        "was",
        "wo",
        "wieso",
        "warum",
        "muss",
        "müssen",
        "musst",
        "darf",
        "dürfen",
        "soll",
        "sollen",
        "kann",
        "können",
        "mit",
        "von",
        "vom",
        "für",
        "im",
        "in",
        "ins",
        "auf",
        "an",
        "am",
        "zu",
        "zum",
        "zur",
        "bei",
        "nach",
        "über",
        "unter",
        "vor",
        "aus",
        "sich",
        "es",
        "man",
        "noch",
        "nicht",
        "nur",
        "auch",
        "als",
        "dann",
        "denn",
        "doch",
        "ja",
        "nein",
        "so",
        "ob",
        "wenn",
        "dass",
        "da",
        "hier",
        "dort",
        "mein",
        "meine",
        "ich",
        "wir",
        "ihr",
        "sie",
        "er",
        "du",
        "uns",
        "euch",
        "gilt",
        "gelten",
        "gibt",
        "hat",
        "haben",
        "habe",
        "sein",
        "seine",
        "ihre",
        "ihren",
        "beim",
        "mehr",
        "wieviel",
        "wieviele",
        "viele",
        "viel",
        "lange",
        "oft",
        "hoch",
        "höhe",
        "hohe",
        "hoher",
        "jetzt",
        "aktuell",
        "eigentlich",
        "bitte",
        "mal",
        "selbst",
        "darf",
        "dürfen",
        "genau",
        "eigentlich",
        "überhaupt",
        "damit",
        "dafür",
        "dabei",
        "deshalb",
        "trotzdem",
        "schon",
        "immer",
        "etwa",
        "the",
        "a",
        "an",
        "of",
        "to",
        "for",
        "is",
        "are",
        "what",
        "how",
        "when",
        "which",
        "who",
    ]
)

_WORD = re.compile(r"[a-zäöüß0-9][a-zäöüß0-9\-]*", re.IGNORECASE)
_NUMBER = re.compile(r"\d{1,2}:\d{2}|\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def fold(s: str) -> str:
    return s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def apply_thesaurus(question: str, thesaurus: dict[str, str]) -> str:
    """Adds the policy's own term next to a colloquial one ("Hotel" -> "Hotel übernachtung")."""
    q = question
    low = question.lower()
    words = re.findall(r"[a-zäöüß\-]+", low)
    extra = [
        target
        for term, target in thesaurus.items()
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", low)
        # also as part of a compound ("Hotelübernachtung" contains "hotel")
        or (
            len(term) >= 5
            and " " not in term
            and any(w != term and (w.startswith(term) or w.endswith(term)) for w in words)
        )
    ]
    if extra:
        q = f"{q} {' '.join(extra)}"
    return q


_STEMMER = snowballstemmer.stemmer("german")


def stem(w: str) -> str:
    """Snowball German stem; a participle's "ge-" prefix is dropped ("gesperrt" meets "sperren")."""
    s: str = _STEMMER.stemWord(w.lower())
    if s.startswith("ge") and len(s) > 6 and w.lower().endswith(("t", "en")):
        s = s[2:]
    return s


def content_words(text: str) -> list[str]:
    """Words that carry meaning, split at hyphens ("Vier-Augen-Prinzip" -> vier, augen, prinzip)."""
    out: list[str] = []
    for m in _WORD.finditer(text):
        for part in m.group(0).split("-"):
            p = part.lower()
            if len(p) >= 3 and p not in STOPWORDS and not p.isdigit():
                out.append(p)
    return out


def stems(text: str) -> set[str]:
    return {stem(w) for w in content_words(text)}


def same_stem(q: str, t: str) -> bool:
    """Equal; or the longer is a compound ending in the shorter (German compounds name the thing
    last: a "Benutzerkonto" is a "Konto"); or the same word with a different ending."""
    if q == t:
        return True
    short, long = (q, t) if len(q) <= len(t) else (t, q)
    if len(short) < 4:
        return False
    # A long word at the start of a compound ("Geldwäsche" in "Geldwäscheprävention") still names
    # the topic; a short one ("Kredit" in "Kreditkarte") does not.
    return long.endswith(short) or (long.startswith(short) and (len(long) - len(short) <= 3 or len(short) >= 7))


class Vocabulary:
    """Stem frequencies over the indexed paragraphs, and each document version's stems."""

    def __init__(
        self, texts: list[str], docs: dict[tuple[str, int], str] | None = None, unknown_weight: float = 1.0
    ) -> None:
        self.n = max(1, len(texts))
        self.unknown_weight = unknown_weight
        self.df: Counter[str] = Counter()
        for t in texts:
            self.df.update(stems(t))
        self.docs = {k: stems(v) for k, v in (docs or {}).items()}
        self._cache: dict[str, int] = {}

    def frequency(self, s: str) -> int:
        """Paragraphs that contain the stem or a word it matches (compounds, endings)."""
        if s not in self._cache:
            self._cache[s] = sum(n for t, n in self.df.items() if same_stem(s, t))
        return self._cache[s]

    def known(self, s: str) -> bool:
        return self.frequency(s) > 0

    def weight(self, s: str) -> float:
        # A word no paragraph uses can be the point of the question ("Probezeit": then nothing
        # answers it) or chat around it ("eine Flasche Wein"); it weighs a configured share of the
        # rarest word's weight (config/retrieval.yaml: unknown_word_weight).
        f = self.frequency(s)
        top = math.log(1 + self.n)
        return top * self.unknown_weight if f == 0 else math.log(1 + self.n / f)

    def anchor(self, question: str) -> str | None:
        """The rarest noun of the question that the policies use at all. German capitalises nouns;
        a question typed in lower case falls back to all its words."""
        words = [m.group(0) for m in _WORD.finditer(question)][1:]
        nouns = {stem(p) for w in words if w[:1].isupper() for p in w.split("-") if len(p) >= 3}
        pool = {q for q in (nouns or stems(question)) if q not in STOPWORDS and self.known(q)}
        return max(pool, key=lambda q: (self.weight(q), q)) if pool else None

    def in_document(self, s: str, doc_key: str, version: int) -> bool:
        body = self.docs.get((doc_key, version), set())
        return s in body or any(same_stem(s, t) for t in body)


def overlap(question_stems: set[str], text_stems: set[str], vocab: Vocabulary | None = None) -> float:
    """Share of the question's (weighted) stems that the text contains."""
    if not question_stems:
        return 0.0
    total = hit = 0.0
    for q in question_stems:
        w = vocab.weight(q) if vocab else 1.0
        total += w
        if q in text_stems or any(same_stem(q, t) for t in text_stems):
            hit += w
    return hit / total


# What kind of value a question asks for, and what kinds a paragraph states.
AMOUNT, DURATION, TIME, FREQUENCY, ROLE = "amount", "duration", "time", "frequency", "role"

_Q_TYPES: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = (
    (
        re.compile(r"\bwie oft\b|\bhäufig|\bturnus|\bintervall|\babst(a|ä)nd|\bwie regelmäßig|\brhythmus", re.I),
        frozenset({FREQUENCY, DURATION}),
    ),
    (re.compile(r"\bwer\b|\bwem\b|\bwelche (stelle|person|funktion)|\bzuständig", re.I), frozenset({ROLE})),
    (re.compile(r"\bwie lang\b", re.I), frozenset({AMOUNT, DURATION})),
    (
        re.compile(
            r"\bwie lange\b|\bfrist|\bbis wann\b|\bwann\b|\bwie schnell\b|\bin welcher zeit|\bwie viele (tage|stunden|wochen|monate|jahre)|"
            r"\ban wie vielen tagen|\bwie viele (arbeits|geschäfts|kalender)?tage|\bdauer|\bnach welcher|\bhaltedauer|\w*zeit\b|"
            r"\bannahmeschluss|\bwie früh|\bwie spät|\baufbewahr|\baufheben|\bgespeichert",
            re.I,
        ),
        frozenset({DURATION, TIME}),
    ),
    (
        re.compile(
            r"\bbetrag|\bwert\b|\bwertgrenze|\bauftragswert|\blimit|\bgrenze\b|\bwie hoch|\bwie viel\b|\bkosten|\babschlag|"
            r"\bquote|\bmindestwert|\bratingklasse|\bauslauf|\bmindestlänge|\bobligo|\bverlust|\bwie viele zeichen|\bsumme|"
            r"\bobergrenze|\bhöchst|\bmaximal|\bprozent|\bhaircut|\bab wie viel",
            re.I,
        ),
        frozenset({AMOUNT}),
    ),
)

_P_TYPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (AMOUNT, re.compile(r"\d[\d.,]*\s*(EUR|Euro|%|Zeichen)|\bRatingklasse\s+\d|Ratingklasse\b", re.I)),
    (
        DURATION,
        re.compile(
            r"\d+\s*(Minuten?|Stunden?|(Kalender|Geschäfts|Arbeits)?[Tt]ag(e|en)?|Wochen?|Monat(e|en)?|Jahr(e|en)?)\b|"
            r"\b(einem|einen|zwei|drei|vier|sechs) (Monat|Monate|Wochen|Jahre)\b|vor Ausführung",
            re.I,
        ),
    ),
    (TIME, re.compile(r"\b\d{1,2}:\d{2}\s*Uhr", re.I)),
    (
        FREQUENCY,
        re.compile(
            r"\b(jährlich|halbjährlich|monatlich|wöchentlich|täglich|quartalsweise|alle \w+ (Jahre|Monate))\b", re.I
        ),
    ),
    (
        ROLE,
        re.compile(
            r"\b(Geschäftsleitung|Vorstand|Mitglied|Ausschuss|Leitung|Beauftragte\w*|Bereichsleitung|Compliance)\b"
        ),
    ),
)


def asked_types(question: str) -> frozenset[str] | None:
    """Kinds of value the question asks for, or None if it does not ask for a value. The first
    matching cue decides: "Wie oft muss der Wert ... überprüft werden" asks for a frequency."""
    for pattern, kinds in _Q_TYPES:
        if pattern.search(question):
            return kinds
    return None


def stated_types(text: str) -> frozenset[str]:
    return frozenset(kind for kind, pattern in _P_TYPES if pattern.search(text))


def numbers(text: str) -> set[str]:
    """Numbers as written ("25.000", "15:00", "1,5"), normalised to digits and separators."""
    return {m.group(0).replace(".", "") if ":" not in m.group(0) else m.group(0) for m in _NUMBER.finditer(text)}


def tsquery_terms(question: str) -> str:
    """An OR query for Postgres full-text search; to_tsquery('german') stems each term."""
    words = sorted({re.sub(r"[^a-zäöüß0-9]", "", w) for w in content_words(question)} - {""})
    return " | ".join(words)


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


class SketchEmbedder:
    """Signed feature hashing of character n-grams and words into `dim` dimensions."""

    def __init__(self, dim: int = 384, probes: int = 2) -> None:
        self.dim = dim
        self.probes = probes

    def _features(self, text: str) -> Counter[str]:
        feats: Counter[str] = Counter()
        for w in content_words(text):
            f = fold(w)
            feats[f"w:{f}"] += 1
            padded = f" {f} "
            for n in (3, 4, 5):
                for i in range(len(padded) - n + 1):
                    feats[padded[i : i + n]] += 1
        return feats

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feat, tf in self._features(text).items():
                weight = 1.0 + math.log(tf)
                h = hashlib.blake2b(feat.encode(), digest_size=8 * self.probes).digest()
                for k in range(self.probes):
                    v = int.from_bytes(h[8 * k : 8 * k + 8], "little")
                    out[row, v % self.dim] += weight if (v >> 63) & 1 else -weight
            norm = float(np.linalg.norm(out[row]))
            if norm > 0:
                out[row] /= norm
        return out
