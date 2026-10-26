"""
Development questions, generated from the world's truth (the blind set is written separately, see
blind/BRIEF.md). Each question has a user, a date, and either the expected value with the paragraph
that states it, or the expectation that nothing is answered.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta

from .world import World, can_read

NOT_COVERED = (
    "Wie hoch ist das Budget für die Weihnachtsfeier einer Abteilung?",
    "Welche Dienstwagen dürfen Bereichsleiter fahren?",
    "Wie viele Urlaubstage haben Auszubildende im ersten Jahr?",
    "Ab welchem Betrag braucht ein Dispositionskredit eine Schufa-Auskunft?",
    "Welche Kryptowährungen dürfen Kunden über die Bank handeln?",
    "Wie hoch ist der Zuschuss für das Jobticket?",
    "Welche Farbe muss das Logo auf Präsentationen haben?",
    "Bis zu welchem Betrag dürfen Geldautomaten nachts befüllt werden?",
    "Wie lange dauert die Probezeit für neue Mitarbeitende?",
    "Welche Zinsen bekommen Mitarbeitende auf ihr Tagesgeldkonto?",
    "Ab wann gilt die Pflicht zur Zeiterfassung im Vertrieb?",
    "Wie viele Kreditkarten darf ein Privatkunde haben?",
)


@dataclass(frozen=True)
class Question:
    id: str
    user: str
    as_of: str
    question: str
    expect: str  # answer | no_answer
    value: str | None
    doc_no: str | None
    version: int | None
    tz: str | None
    kind: str


def _reader(world: World, doc_no: str) -> str:
    """A user who may read the policy, preferring one from its owning department."""
    p = world.policy(doc_no)
    readers = [u for u in world.users if can_read(u, p)]
    own = [u for u in readers if p.owner in u.departments]
    return (own or readers)[0].login


def _outsider(world: World, doc_no: str) -> str | None:
    p = world.policy(doc_no)
    out = [u for u in world.users if not can_read(u, p)]
    return out[0].login if out else None


def dev_questions(world: World) -> list[Question]:
    out: list[Question] = []
    n = 0

    def add(**kw: object) -> None:
        nonlocal n
        n += 1
        out.append(Question(id=f"d{n:03d}", **kw))  # type: ignore[arg-type]

    for p in world.policies:
        for f in p.facts:
            for version, start in enumerate(p.versions, start=1):
                end = p.versions[version] if version < len(p.versions) else date(2026, 10, 26)
                on = start + (end - start) / 2
                t = world.truth(f.id, on)
                assert t is not None and t.version == version
                q = f.questions[(version - 1) % len(f.questions)]
                add(
                    user=_reader(world, p.doc_no),
                    as_of=on.isoformat(),
                    question=q,
                    expect="answer",
                    value=t.value,
                    doc_no=p.doc_no,
                    version=version,
                    tz=t.tz,
                    kind="current" if version == len(p.versions) else "past",
                )
            outsider = _outsider(world, p.doc_no)
            # A rule that restates a supervisory circular is answered by the circular, which
            # everyone may read; asking it as an outsider is not a permission test.
            if outsider and "vgl. AM" not in f.statements[0]:
                t = world.truth(f.id, date(2026, 10, 26))
                assert t is not None
                add(
                    user=outsider,
                    as_of="2026-10-26",
                    question=f.questions[0],
                    expect="no_answer",
                    value=t.value,
                    doc_no=p.doc_no,
                    version=None,
                    tz=None,
                    kind="no_access",
                )
        before = p.versions[0] - timedelta(days=40)
        add(
            user=_reader(world, p.doc_no),
            as_of=before.isoformat(),
            question=p.facts[0].questions[0],
            expect="no_answer",
            value=None,
            doc_no=None,
            version=None,
            tz=None,
            kind="before_first",
        )
    for i, q in enumerate(NOT_COVERED):
        add(
            user=world.users[i % len(world.users)].login,
            as_of="2026-10-26",
            question=q,
            expect="no_answer",
            value=None,
            doc_no=None,
            version=None,
            tz=None,
            kind="not_covered",
        )
    return out


def as_dicts(qs: list[Question]) -> list[dict[str, object]]:
    return [asdict(q) for q in qs]
