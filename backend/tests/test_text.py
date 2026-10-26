import numpy as np

from copilot.answer.redact import redact
from copilot.text import (
    AMOUNT,
    DURATION,
    FREQUENCY,
    ROLE,
    TIME,
    SketchEmbedder,
    Vocabulary,
    apply_thesaurus,
    asked_types,
    numbers,
    overlap,
    same_stem,
    stated_types,
    stem,
    stems,
)


def test_stems_meet_inflections_participles_and_compounds() -> None:
    assert stem("gesperrt")[:5] == stem("sperren")[:5]
    assert same_stem(stem("Konten"), stem("Benutzerkonten"))  # a Benutzerkonto is a Konto
    assert same_stem(stem("Geldwäsche"), stem("Geldwäscheprävention"))  # long modifier names the topic
    assert not same_stem(stem("Kredit"), stem("Kreditkarte"))  # a Kreditkarte is not a Kredit


def test_overlap_weights_rare_words() -> None:
    v = Vocabulary(["Zahlung freigeben", "Zahlung prüfen", "Zahlung buchen", "Vier-Augen-Prinzip Zahlung"])
    q = stems("Vier-Augen-Prinzip Zahlung")
    assert overlap(q, stems("Vier-Augen-Prinzip"), v) > overlap(q, stems("Zahlung"), v)
    assert v.anchor("Wann gilt das Vier-Augen-Prinzip bei einer Zahlung?") in {
        stem("Prinzip"),
        stem("Augen"),
        stem("Vier"),
    }


def test_answer_types() -> None:
    assert asked_types("Ab welchem Betrag gilt die Grenze?") == {AMOUNT}
    assert asked_types("Wie oft muss der Wert überprüft werden?") == {FREQUENCY, DURATION}  # first cue decides
    assert asked_types("Bis wann muss die Überweisung da sein?") == {DURATION, TIME}
    assert asked_types("Wer muss zustimmen?") == {ROLE}
    assert asked_types("Was regelt die Richtlinie?") is None
    assert stated_types("ab einem Betrag von 25.000 EUR") == {AMOUNT}
    assert stated_types("innerhalb von 1 Tag") == {DURATION}
    assert stated_types("ist 16:00 Uhr") == {TIME}
    assert FREQUENCY in stated_types("mindestens jährlich zu testen")
    assert ROLE in stated_types("der Zustimmung durch ein Mitglied der Geschäftsleitung")


def test_thesaurus_applies_to_compounds() -> None:
    th = {"hotel": "übernachtung", "instant payment": "echtzeitüberweisung"}
    assert "übernachtung" in apply_thesaurus("Was darf eine Hotelübernachtung kosten?", th)
    assert "echtzeitüberweisung" in apply_thesaurus("Limit für ein Instant Payment?", th)
    assert apply_thesaurus("Wie hoch ist das Limit?", th) == "Wie hoch ist das Limit?"


def test_numbers_as_written() -> None:
    assert numbers("ab 25.000 EUR bis 16:00 Uhr, 1,5 qmm") == {"25000", "16:00", "1,5"}


def test_embedding_is_deterministic_and_lexically_sensible() -> None:
    e = SketchEmbedder(384)
    a, b, c = e.embed(["Übernachtungskosten auf Dienstreisen", "Übernachtung Dienstreise", "Passwortlänge"])
    assert np.allclose(e.embed(["Übernachtungskosten auf Dienstreisen"])[0], a)
    assert float(a @ b) > float(a @ c)
    assert abs(float(np.linalg.norm(a)) - 1.0) < 1e-5


def test_redaction_removes_personal_data() -> None:
    text, found = redact("Kunde DE89 3704 0044 0532 0130 00, max@kunde.example, Tel. 030 1234567, Kundennummer 9876543")
    assert "DE89" not in text and "max@" not in text and "1234567" not in text and "9876543" not in text
    assert set(found) == {"IBAN", "E-MAIL", "TELEFON", "KUNDENNUMMER"}
