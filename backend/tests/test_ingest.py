"""Re-running ingestion, conflicting versions, late versions, and classification conflicts."""

import json
import shutil
from pathlib import Path

import psycopg
import pytest

from copilot.config import retrieval_config
from copilot.db import as_system
from copilot.ingest.pipeline import ingest_export
from copilot.text import SketchEmbedder

pytestmark = pytest.mark.db


def test_the_same_export_twice_changes_nothing(pool, export_dir: Path) -> None:  # type: ignore[no-untyped-def]
    with as_system(pool) as conn:
        before = conn.execute("SELECT count(*) AS n FROM paragraphs").fetchone()["n"]
        report = ingest_export(conn, export_dir, SketchEmbedder(retrieval_config().embedding_dim))
        after = conn.execute("SELECT count(*) AS n FROM paragraphs").fetchone()["n"]
    assert report.new_versions == 0 and report.unchanged == report.files and before == after


def test_a_changed_file_under_an_existing_version_is_rejected(pool, export_dir: Path, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "x"
    folder.mkdir()
    listing = json.loads((export_dir / "listing.json").read_text(encoding="utf-8"))
    entry = next(e for e in listing if e["path"].endswith(".html") and e["path"].startswith("RL-"))
    html = (
        (export_dir / entry["path"])
        .read_text(encoding="utf-8")
        .replace("in der Havelsee Bank AG", "in der Havelsee Bank AG und ihren Töchtern", 1)
    )
    (folder / entry["path"]).write_text(html, encoding="utf-8")
    (folder / "listing.json").write_text(json.dumps([entry]), encoding="utf-8")
    with as_system(pool) as conn:
        report = ingest_export(conn, folder, SketchEmbedder(retrieval_config().embedding_dim))
    assert report.new_versions == 0
    assert "already ingested with different content" in report.rejected[0]["reason"]


def test_validity_follows_the_dates_even_when_versions_arrive_late(pool) -> None:  # type: ignore[no-untyped-def]
    with as_system(pool) as conn:
        rows = conn.execute(
            """SELECT version, valid_from, valid_to FROM document_versions v JOIN documents d ON d.id = v.document_id
                WHERE d.doc_key = 'RL-ZV-01' ORDER BY version"""
        ).fetchall()
    assert [r["valid_to"] for r in rows[:-1]] == [r["valid_from"] for r in rows[1:]]
    assert rows[-1]["valid_to"] is None


def test_stricter_header_classification_wins(pool, database, export_dir: Path, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "y"
    folder.mkdir()
    listing = json.loads((export_dir / "listing.json").read_text(encoding="utf-8"))
    entry = next(
        e
        for e in listing
        if e["path"].startswith("RL-") and e["path"].endswith("_v1.html") and e["classification"] <= 2
    )
    src = export_dir / entry["path"]
    key = entry["path"].split("_v1")[0]
    name = "RL-XX-99_v1.html"
    level = {1: "öffentlich", 2: "intern"}[entry["classification"]]
    text = src.read_text(encoding="utf-8").replace(key, "RL-XX-99").replace(f"<td>{level}</td>", "<td>vertraulich</td>")
    (folder / name).write_text(text, encoding="utf-8")
    (folder / "listing.json").write_text(json.dumps([{**entry, "path": name}]), encoding="utf-8")
    with as_system(pool) as conn:
        report = ingest_export(conn, folder, SketchEmbedder(retrieval_config().embedding_dim))
        level = conn.execute("SELECT classification FROM documents WHERE doc_key = 'RL-XX-99'").fetchone()[
            "classification"
        ]
    # The app role may not delete anything; clean up as the owner.
    with psycopg.connect(database["admin"], autocommit=True) as admin:
        admin.execute("DELETE FROM paragraphs WHERE doc_key = 'RL-XX-99'")
        admin.execute(
            "DELETE FROM document_versions WHERE document_id = (SELECT id FROM documents WHERE doc_key = 'RL-XX-99')"
        )
        admin.execute("DELETE FROM documents WHERE doc_key = 'RL-XX-99'")
    assert level == 3 and "stricter" in report.warnings[0]
    shutil.rmtree(folder)
