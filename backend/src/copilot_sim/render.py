"""
Lays the policies out as documents and writes them the way a bank's document management system
would export them: Word files, PDFs and HTML pages (from a wiki), plus a listing of the export with
each file's path and access groups.

Every policy version has the same layout: a header block, "1 Zweck und Geltungsbereich", a
section per group of rules, "Änderungshistorie" and "Inkrafttreten". Paragraphs are numbered
"Tz. <section>.<n>". The change history repeats old and new values on purpose: it is where a
careless retriever finds the wrong number.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .world import DEPARTMENTS, LEVELS, Circular, Policy, World


@dataclass(frozen=True)
class Para:
    tz: str
    text: str
    fact: str | None = None


@dataclass(frozen=True)
class Section:
    number: int
    title: str
    paras: tuple[Para, ...]


@dataclass(frozen=True)
class Doc:
    doc_no: str
    title: str
    version: int
    valid_from: date
    level: int
    owner: str
    audience: tuple[str, ...]
    references: tuple[str, ...]
    sections: tuple[Section, ...]


def de_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def audience_text(p: Policy) -> str:
    if "alle" in p.audience:
        return "alle Mitarbeitenden der Havelsee Bank AG"
    return "die Bereiche " + ", ".join(DEPARTMENTS[a] for a in p.audience)


def layout(world: World, p: Policy, version: int) -> Doc:
    """The document for one version. Also records each rule's paragraph number in world.tz."""
    v = version - 1
    sections: list[Section] = []
    intro = (
        Para("1.1", f"Diese Richtlinie regelt {p.topic or 'die Abläufe des Bereichs'} in der Havelsee Bank AG."),
        Para("1.2", f"Sie gilt für {audience_text(p)}."),
        Para(
            "1.3",
            f"Verantwortlich für Pflege und jährliche Überprüfung dieser Richtlinie ist der Bereich "
            f"{DEPARTMENTS[p.owner]}. Ausnahmen bedürfen der vorherigen schriftlichen Zustimmung dieses Bereichs.",
        ),
    )
    sections.append(Section(1, "Zweck und Geltungsbereich", intro))

    groups: dict[str, list] = {}
    for f in p.facts:
        groups.setdefault(f.section, []).append(f)
    for n, (title, facts) in enumerate(groups.items(), start=2):
        paras = []
        for i, f in enumerate(facts, start=1):
            tz = f"{n}.{i}"
            world.tz[(p.doc_no, f.id)] = tz
            stmt = f.statements[0].format(v=f.values[v])
            paras.append(Para(tz, stmt, f.id))
        paras.append(
            Para(
                f"{n}.{len(facts) + 1}",
                "Die Einhaltung dieser Vorgaben ist nachvollziehbar zu dokumentieren und wird von der "
                "Internen Revision risikoorientiert geprüft.",
            )
        )
        sections.append(Section(n, title, tuple(paras)))

    history: list[Para] = []
    k = len(sections) + 1
    for ver in range(2, version + 1):
        changed = [f for f in p.facts if f.values[ver - 2] != f.values[ver - 1]]
        if not changed:
            continue
        parts = "; ".join(f"{f.section}: von {f.values[ver - 2]} auf {f.values[ver - 1]}" for f in changed)
        history.append(Para(f"{k}.{len(history) + 1}", f"Version {ver} vom {de_date(p.versions[ver - 1])}: {parts}."))
    if history:
        sections.append(Section(k, "Änderungshistorie", tuple(history)))
        k += 1
    ref = f" Sie setzt {', '.join(p.references)} um." if p.references else ""
    sections.append(
        Section(
            k,
            "Inkrafttreten",
            (
                Para(
                    f"{k}.1",
                    f"Diese Fassung tritt am {de_date(p.versions[v])} in Kraft und ersetzt alle früheren Fassungen.{ref}",
                ),
            ),
        )
    )
    return Doc(p.doc_no, p.title, version, p.versions[v], p.level, p.owner, p.audience, p.references, tuple(sections))


def circular_doc(c: Circular, version: int) -> Doc:
    paras = tuple(Para(tz, texts[version - 1]) for tz, texts in c.paragraphs)
    return Doc(c.ref, c.title, version, c.versions[version - 1], 1, "EXT", ("alle",), (), (Section(1, "Text", paras),))


def header_lines(d: Doc) -> list[tuple[str, str]]:
    lines = [
        ("Dokumentnummer", d.doc_no),
        ("Version", str(d.version)),
        ("Gültig ab", de_date(d.valid_from)),
        ("Klassifizierung", LEVELS[d.level]),
    ]
    if d.owner != "EXT":
        lines.append(("Verantwortlich", DEPARTMENTS[d.owner]))
    if d.references:
        lines.append(("Bezug", ", ".join(d.references)))
    return lines


def to_docx(d: Doc, path: Path) -> None:
    doc = Document()
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.add_heading(d.title, level=0)
    table = doc.add_table(rows=0, cols=2)
    for k, v in header_lines(d):
        row = table.add_row().cells
        row[0].text, row[1].text = k, v
    for s in d.sections:
        doc.add_heading(f"{s.number} {s.title}", level=1)
        for para in s.paras:
            doc.add_paragraph(f"Tz. {para.tz} {para.text}")
    doc.save(str(path))


def to_pdf(d: Doc, path: Path) -> None:
    styles = getSampleStyleSheet()
    story = [Paragraph(html.escape(d.title), styles["Title"])]
    for k, v in header_lines(d):
        story.append(Paragraph(f"{html.escape(k)}: {html.escape(v)}", styles["Normal"]))
    for s in d.sections:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f"{s.number} {html.escape(s.title)}", styles["Heading2"]))
        for para in s.paras:
            story.append(Paragraph(f"Tz. {para.tz} {html.escape(para.text)}", styles["BodyText"]))
    SimpleDocTemplate(str(path), pagesize=A4, title=d.title).build(story)


def to_html(d: Doc) -> str:
    rows = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in header_lines(d))
    body = "".join(
        f"<h2>{s.number} {html.escape(s.title)}</h2>"
        + "".join(f'<p><span class="tz">Tz. {p.tz}</span> {html.escape(p.text)}</p>' for p in s.paras)
        for s in d.sections
    )
    return (
        f'<!doctype html><html lang="de"><head><meta charset="utf-8"><title>{html.escape(d.title)}</title></head>'
        f'<body><div class="wiki-page"><h1>{html.escape(d.title)}</h1><table class="meta">{rows}</table>'
        f"{body}</div></body></html>"
    )


def to_markdown(d: Doc) -> str:
    out = [f"# {d.title}", ""] + [f"- {k}: {v}" for k, v in header_lines(d)] + [""]
    for s in d.sections:
        out += [f"## {s.number} {s.title}", ""] + [f"Tz. {p.tz} {p.text}" for p in s.paras] + [""]
    return "\n".join(out)


FORMATS = ("docx", "pdf", "html")


def acl_groups(p: Policy) -> list[str]:
    """The groups the document management system grants read access to (dept and clearance)."""
    depts = ["all-staff"] if "alle" in p.audience else [f"dept-{a.lower()}" for a in p.audience]
    return [*depts, "audit-all"]


def export(world: World, out: Path, *, markdown: Path | None = None) -> list[dict]:
    """Writes every version of every document; returns (and writes) the system's file listing."""
    out.mkdir(parents=True, exist_ok=True)
    listing: list[dict] = []
    for i, p in enumerate(world.policies):
        fmt = FORMATS[i % len(FORMATS)]
        for version in range(1, len(p.versions) + 1):
            d = layout(world, p, version)
            name = f"{p.doc_no}_v{version}.{fmt}"
            path = out / name
            if fmt == "docx":
                to_docx(d, path)
            elif fmt == "pdf":
                to_pdf(d, path)
            else:
                path.write_text(to_html(d), encoding="utf-8")
            if markdown:
                markdown.mkdir(parents=True, exist_ok=True)
                (markdown / f"{p.doc_no}_v{version}.md").write_text(to_markdown(d), encoding="utf-8")
            listing.append(
                {
                    "path": name,
                    "source": "dms" if fmt != "html" else "wiki",
                    "classification": p.level,
                    "read_groups": acl_groups(p),
                }
            )
    for c in world.circulars:
        for version in range(1, len(c.versions) + 1):
            d = circular_doc(c, version)
            name = f"{c.ref.replace(' ', '_').replace('/', '-')}_v{version}.html"
            (out / name).write_text(to_html(d), encoding="utf-8")
            if markdown:
                (markdown / name.replace(".html", ".md")).write_text(to_markdown(d), encoding="utf-8")
            listing.append(
                {"path": name, "source": "regulatory-feed", "classification": 1, "read_groups": ["all-staff"]}
            )
    (out / "listing.json").write_text(json.dumps(listing, indent=2, ensure_ascii=False), encoding="utf-8")
    users = [
        {
            "login": u.login,
            "name": u.name,
            "title": u.title,
            "clearance": u.clearance,
            "groups": ["all-staff"]
            + [f"dept-{d.lower()}" for d in u.departments]
            + (["audit-all"] if u.auditor else [])
            + (["copilot-reviewer"] if "CO" in u.departments else []),
        }
        for u in world.users
    ]
    (out / "users.json").write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")
    return listing
