from pathlib import Path

import pytest

from copilot.ingest.parse import ParseError, parse
from copilot_sim.render import layout
from copilot_sim.world import World


def test_every_format_parses_to_the_laid_out_document(export_dir: Path) -> None:
    world = World()
    files = sorted(p for p in export_dir.iterdir() if p.suffix in {".docx", ".pdf", ".html"})
    assert {p.suffix for p in files} == {".docx", ".pdf", ".html"}
    for f in files:
        doc = parse(f)
        if doc.doc_key.startswith("AM "):
            continue
        expected = layout(world, world.policy(doc.doc_key), doc.version)
        assert doc.title == expected.title
        assert [(p.tz, p.section, p.text) for p in doc.paragraphs] == [
            (p.tz, s.title, p.text) for s in expected.sections for p in s.paras
        ]
        assert doc.valid_from == expected.valid_from and doc.classification == expected.level


def test_a_document_without_its_header_is_rejected(tmp_path: Path) -> None:
    f = tmp_path / "x.html"
    f.write_text("<html><body><h1>Ohne Kopf</h1><h2>1 Zweck</h2><p>Tz. 1.1 Text.</p></body></html>", encoding="utf-8")
    with pytest.raises(ParseError, match="missing header fields"):
        parse(f)


def test_duplicate_paragraph_numbers_are_rejected(tmp_path: Path) -> None:
    f = tmp_path / "x.html"
    meta = "".join(
        f"<tr><th>{k}</th><td>{v}</td></tr>"
        for k, v in {
            "Dokumentnummer": "X-1",
            "Version": "1",
            "Gültig ab": "01.01.2025",
            "Klassifizierung": "intern",
        }.items()
    )
    f.write_text(
        f'<h1>T</h1><table class="meta">{meta}</table><h2>1 A</h2><p>Tz. 1.1 a</p><p>Tz. 1.1 b</p>', encoding="utf-8"
    )
    with pytest.raises(ParseError, match="twice"):
        parse(f)
