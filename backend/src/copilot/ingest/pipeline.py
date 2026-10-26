"""
Ingestion: reads an export of the document management system (a listing with each file's path,
source, classification and read groups), parses each file, and stores new versions with their
paragraphs, validity periods and embeddings. Re-running on the same export changes nothing.

Access comes from the source system's listing, not from the document text: a header can be wrong,
a permission export is what the bank's systems enforce. When the header's classification is
stricter than the listing's, the stricter one wins and the run records a warning.

When a supervisory circular gets a new version, the paragraphs that changed are matched to the
internal policy paragraphs that implement them, and each match becomes an impact item to review.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from ..db import Conn
from ..text import Embedder
from .parse import ParsedDocument, ParseError, parse

HISTORY = re.compile(r"änderung|historie|versionsverlauf", re.I)


@dataclass
class RunReport:
    files: int = 0
    new_versions: int = 0
    unchanged: int = 0
    rejected: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    impact_items: int = 0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_users(conn: Conn, users: list[dict[str, Any]]) -> int:
    """Mirrors the identity provider's export (login, clearance, groups)."""
    for u in users:
        conn.execute(
            """INSERT INTO users (login, name, title, clearance, groups) VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (login) DO UPDATE SET name = excluded.name, title = excluded.title,
                 clearance = excluded.clearance, groups = excluded.groups""",
            (u["login"], u["name"], u.get("title", ""), u["clearance"], u["groups"]),
        )
    return len(users)


def _store_version(
    conn: Conn, doc: ParsedDocument, entry: dict[str, Any], digest: str, embedder: Embedder, report: RunReport
) -> int:
    kind = "circular" if entry["source"] == "regulatory-feed" else "policy"
    classification = int(entry["classification"])
    if doc.classification > classification:
        report.warnings.append(
            f"{doc.doc_key} v{doc.version}: header says classification {doc.classification}, "
            f"source system {classification}; using the stricter {doc.classification}"
        )
        classification = doc.classification
    row = conn.execute(
        """INSERT INTO documents (doc_key, title, kind, source, classification, read_groups, owner, references_)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (doc_key) DO UPDATE SET title = excluded.title, classification = excluded.classification,
             read_groups = excluded.read_groups, references_ = excluded.references_
           RETURNING id""",
        (
            doc.doc_key,
            doc.title,
            kind,
            entry["source"],
            classification,
            entry["read_groups"],
            doc.fields.get("Verantwortlich"),
            doc.references,
        ),
    ).fetchone()
    assert row is not None
    document_id = row["id"]
    vrow = conn.execute(
        """INSERT INTO document_versions (document_id, version, valid_from, file_name, file_sha256, paragraphs)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (document_id, doc.version, doc.valid_from, entry["path"], digest, len(doc.paragraphs)),
    ).fetchone()
    assert vrow is not None
    version_id = vrow["id"]
    vectors = embedder.embed([f"{doc.title}. {p.section}. {p.text}" for p in doc.paragraphs])
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO paragraphs (version_id, doc_key, version, tz, section, is_history, text, text_hash,
                                       valid_from, valid_to, classification, read_groups, embedding)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s)""",
            [
                (
                    version_id,
                    doc.doc_key,
                    doc.version,
                    p.tz,
                    p.section,
                    bool(HISTORY.search(p.section)),
                    p.text,
                    hashlib.sha256(p.text.encode()).hexdigest(),
                    doc.valid_from,
                    classification,
                    entry["read_groups"],
                    vectors[i],
                )
                for i, p in enumerate(doc.paragraphs)
            ],
        )
    _refresh_validity(conn, document_id)
    return int(document_id)


def _refresh_validity(conn: Conn, document_id: int) -> None:
    """Each version is valid until the next version's date of effect (versions may arrive late)."""
    rows = conn.execute(
        "SELECT id, valid_from FROM document_versions WHERE document_id = %s ORDER BY valid_from, version",
        (document_id,),
    ).fetchall()
    for cur, nxt in zip(rows, [*rows[1:], None], strict=True):
        valid_to: date | None = nxt["valid_from"] if nxt else None
        conn.execute("UPDATE document_versions SET valid_to = %s WHERE id = %s", (valid_to, cur["id"]))
        conn.execute("UPDATE paragraphs SET valid_to = %s WHERE version_id = %s", (valid_to, cur["id"]))


def detect_impact(conn: Conn, circular: str, to_version: int, similarity: float = 0.6) -> int:
    """Changed circular paragraphs -> the internal paragraphs that were in force when the change took
    effect and implement it (by explicit reference, or similar wording in a policy that cites the
    circular). If the policy later got a version with a changed paragraph, the item is recorded as
    implemented, with the gap in days; otherwise it stays open for review."""
    rows = conn.execute(
        """SELECT new.tz, old.text AS old_text, new.text AS new_text, new.embedding, new.valid_from
             FROM paragraphs new
             JOIN paragraphs old ON old.doc_key = new.doc_key AND old.version = new.version - 1 AND old.tz = new.tz
            WHERE new.doc_key = %s AND new.version = %s AND old.text_hash <> new.text_hash""",
        (circular, to_version),
    ).fetchall()
    n = 0
    for r in rows:
        ref_pattern = f"%{circular} Tz. {r['tz']}%"
        hits = conn.execute(
            """WITH in_force AS (
                 SELECT p.* FROM paragraphs p
                  WHERE p.valid_from <= %(d)s AND (p.valid_to IS NULL OR p.valid_to > %(d)s)
                    AND p.doc_key <> %(c)s AND NOT p.is_history)
               SELECT p.id, p.doc_key, p.tz, p.text_hash, 'explicit reference' AS reason
                 FROM in_force p WHERE p.text LIKE %(pat)s
               UNION
               SELECT p.id, p.doc_key, p.tz, p.text_hash, 'similar wording' AS reason
                 FROM in_force p JOIN documents d ON d.doc_key = p.doc_key
                WHERE d.kind = 'policy' AND %(c)s = ANY (d.references_)
                  AND 1 - (p.embedding <=> %(e)s) >= %(sim)s AND p.text NOT LIKE %(pat)s""",
            {"c": circular, "pat": ref_pattern, "e": r["embedding"], "sim": similarity, "d": r["valid_from"]},
        ).fetchall()
        for h in hits:
            later = conn.execute(
                """SELECT version, valid_from FROM paragraphs
                    WHERE doc_key = %s AND tz = %s AND valid_from > %s AND text_hash <> %s
                    ORDER BY valid_from LIMIT 1""",
                (h["doc_key"], h["tz"], r["valid_from"], h["text_hash"]),
            ).fetchone()
            status, note = "open", None
            if later:
                gap = (later["valid_from"] - r["valid_from"]).days
                status = "resolved"
                note = f"Umgesetzt in Version {later['version']} vom {later['valid_from']:%d.%m.%Y} ({gap} Tage später)"
            cur = conn.execute(
                """INSERT INTO impact_items (circular, from_version, to_version, circular_tz, change, doc_key,
                                             paragraph_id, reason, status, note)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                (
                    circular,
                    to_version - 1,
                    to_version,
                    r["tz"],
                    f"{r['old_text']} → {r['new_text']}",
                    h["doc_key"],
                    h["id"],
                    h["reason"],
                    status,
                    note,
                ),
            )
            n += cur.rowcount
    return n


def ingest_export(conn: Conn, folder: Path, embedder: Embedder) -> RunReport:
    """Ingests a document export. Run inside a system transaction (db.as_system)."""
    report = RunReport()
    listing: list[dict[str, Any]] = json.loads((folder / "listing.json").read_text(encoding="utf-8"))
    users_file = folder / "users.json"
    if users_file.exists():
        sync_users(conn, json.loads(users_file.read_text(encoding="utf-8")))
    run = conn.execute("INSERT INTO ingestion_runs DEFAULT VALUES RETURNING id").fetchone()
    assert run is not None
    circular_updates: list[tuple[str, int]] = []

    # Oldest version first, so that change detection always has the previous version to compare.
    def order(e: dict[str, Any]) -> tuple[str, int]:
        m = re.search(r"_v(\d+)\.", e["path"])
        return (re.sub(r"_v\d+\..*$", "", e["path"]), int(m.group(1)) if m else 0)

    for entry in sorted(listing, key=order):
        report.files += 1
        path = folder / entry["path"]
        try:
            digest = sha256(path)
            doc = parse(path)
        except (OSError, ParseError, ValueError) as e:
            report.rejected.append({"file": entry["path"], "reason": str(e)})
            continue
        existing = conn.execute(
            """SELECT v.file_sha256 FROM document_versions v JOIN documents d ON d.id = v.document_id
                WHERE d.doc_key = %s AND v.version = %s""",
            (doc.doc_key, doc.version),
        ).fetchone()
        if existing:
            if existing["file_sha256"] == digest:
                report.unchanged += 1
            else:
                report.rejected.append(
                    {
                        "file": entry["path"],
                        "reason": f"{doc.doc_key} version {doc.version} was already ingested with different "
                        "content; publish changes as a new version",
                    }
                )
            continue
        _store_version(conn, doc, entry, digest, embedder, report)
        report.new_versions += 1
        if entry["source"] == "regulatory-feed" and doc.version > 1:
            circular_updates.append((doc.doc_key, doc.version))
    for circular, version in circular_updates:
        report.impact_items += detect_impact(conn, circular, version)
    conn.execute(
        """UPDATE ingestion_runs SET finished_at = now(), files = %s, new_versions = %s, unchanged = %s, rejected = %s
            WHERE id = %s""",
        (report.files, report.new_versions, report.unchanged, Jsonb(report.rejected), run["id"]),
    )
    return report
