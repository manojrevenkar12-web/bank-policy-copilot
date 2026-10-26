"""Removes personal data from questions before they are stored or sent to any model."""

from __future__ import annotations

import re

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b")),
    ("E-MAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("TELEFON", re.compile(r"(?<!\w)(?:\+49|0)[\d\s/-]{7,}\d")),
    ("KUNDENNUMMER", re.compile(r"(?i)\b(kunden(?:nummer|nr\.?)|kd\.?-?nr\.?)\s*[:#]?\s*\d{5,}")),
)


def redact(text: str) -> tuple[str, list[str]]:
    found: list[str] = []
    for label, pattern in PATTERNS:
        if pattern.search(text):
            found.append(label)
            text = pattern.sub(f"[{label}]", text)
    return text, found
