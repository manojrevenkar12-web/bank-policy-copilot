"""End to end through HTTP on the ingested simulated bank (needs PostgreSQL with pgvector)."""

import psycopg
import pytest
from conftest import login

from copilot.api.app import sign, verify_token

pytestmark = pytest.mark.db


def ask(client, who, question, as_of="2026-10-01"):  # type: ignore[no-untyped-def]
    r = client.post("/api/ask", json={"question": question, "as_of": as_of}, headers=login(client, who))
    assert r.status_code == 200, r.text
    return r.json()


def test_answers_with_the_paragraph_in_force_on_the_date(client) -> None:  # type: ignore[no-untyped-def]
    q = "Ab welchem Betrag müssen Zahlungen im Vier-Augen-Prinzip freigegeben werden?"
    then = ask(client, "lena.vogt", q, "2024-02-01")
    now = ask(client, "lena.vogt", q, "2026-10-01")
    assert then["outcome"] == now["outcome"] == "answered"
    assert "15.000 EUR" in then["answer"] and "10.000 EUR" in now["answer"]
    c = then["citations"][0]
    assert (c["doc_key"], c["version"], c["tz"]) == ("RL-ZV-01", 2, "2.1")
    # Asked about the past: the copilot says the rule reads differently today.
    assert then["newer"]["version"] == 3 and "10.000 EUR" in then["newer"]["text"]
    assert now["newer"] is None


def test_nothing_before_the_first_version(client) -> None:  # type: ignore[no-untyped-def]
    r = ask(
        client,
        "lena.vogt",
        "Ab welchem Betrag müssen Zahlungen im Vier-Augen-Prinzip freigegeben werden?",
        "2021-06-01",
    )
    assert r["outcome"] == "no_answer" and r["citations"] == []


def test_a_user_never_sees_what_they_may_not_read(client) -> None:  # type: ignore[no-untyped-def]
    q = "Wie hoch ist das VaR-Limit des Handelsbuchs?"
    trader = ask(client, "felix.brandt", q)
    assert trader["outcome"] == "answered" and "5.500.000 EUR" in trader["answer"]
    for who in ("lena.vogt", "paul.neumann", "tobias.kern"):
        r = ask(client, who, q)
        assert r["outcome"] == "no_answer"
        assert "5.500.000" not in r["answer"]
        assert all(c["doc_key"] != "RL-TR-01" for c in r["trace"]["candidates"])  # not even as evidence
    docs = client.get("/api/documents", headers=login(client, "paul.neumann")).json()
    assert {d["doc_key"] for d in docs} >= {"RL-HR-01", "RL-HR-03"}
    assert "RL-TR-01" not in {d["doc_key"] for d in docs} and "RL-ZV-01" not in {d["doc_key"] for d in docs}
    assert client.get("/api/documents/RL-TR-01/versions/2", headers=login(client, "paul.neumann")).status_code == 404


def test_the_audit_trail_detects_tampering(client, database) -> None:  # type: ignore[no-untyped-def]
    ask(client, "aylin.demir", "Wie lange werden aufgezeichnete Beratungsgespräche aufbewahrt?")
    assert client.get("/api/audit/verify", headers=login(client, "lena.vogt")).status_code == 403
    ok = client.get("/api/audit/verify", headers=login(client, "greta.wolf")).json()
    assert ok["ok"] and ok["records"] >= 1
    with psycopg.connect(database["admin"], autocommit=True) as c:
        qid = c.execute("SELECT max(id) FROM queries").fetchone()[0]
        c.execute("UPDATE queries SET answer = answer || ' (geändert)' WHERE id = %s", (qid,))
    broken = client.get("/api/audit/verify", headers=login(client, "greta.wolf")).json()
    assert broken == {"ok": False, "records": broken["records"], "broken_at": qid}
    with psycopg.connect(database["admin"], autocommit=True) as c:
        c.execute("UPDATE queries SET answer = replace(answer, ' (geändert)', '') WHERE id = %s", (qid,))


def test_the_app_role_cannot_rewrite_history(pool) -> None:  # type: ignore[no-untyped-def]
    from copilot.db import as_system

    with pytest.raises(psycopg.errors.InsufficientPrivilege), as_system(pool) as conn:
        conn.execute("UPDATE queries SET answer = 'x'")


def test_feedback_reaches_reviewers_only(client) -> None:  # type: ignore[no-untyped-def]
    r = ask(client, "aylin.demir", "Wie lange werden aufgezeichnete Beratungsgespräche aufbewahrt?")
    h = login(client, "aylin.demir")
    assert (
        client.post(
            f"/api/queries/{r['query_id']}/feedback", json={"helpful": False, "comment": "Quelle unklar"}, headers=h
        ).status_code
        == 200
    )
    assert client.post(f"/api/queries/{r['query_id']}/feedback", json={"helpful": False}, headers=h).status_code == 409
    other = login(client, "lena.vogt")
    assert (
        client.post(f"/api/queries/{r['query_id']}/feedback", json={"helpful": True}, headers=other).status_code == 404
    )
    assert client.get("/api/review", headers=other).status_code == 403
    queue = client.get("/api/review", headers=login(client, "miriam.haas")).json()
    item = next(i for i in queue if i["query_id"] == r["query_id"])
    done = client.post(
        f"/api/review/{item['id']}/resolve", json={"resolution": "Tz. ergänzt"}, headers=login(client, "miriam.haas")
    )
    assert done.status_code == 200
    assert all(i["id"] != item["id"] for i in client.get("/api/review", headers=login(client, "miriam.haas")).json())


def test_circular_changes_become_impact_items(client) -> None:  # type: ignore[no-untyped-def]
    items = client.get("/api/impact", headers=login(client, "miriam.haas")).json()
    by = {(i["circular"], i["doc_key"]): i for i in items}
    it04 = by[("AM 2/2024", "RL-IT-04")]
    assert it04["status"] == "resolved" and "Version 2" in it04["note"]  # implemented 43 days later
    au01 = by[("AM 1/2023", "RL-AU-01")]
    assert au01["status"] == "open" and "sechs Wochen" in au01["change"]  # the policy still says 4 weeks
    assert client.get("/api/impact", headers=login(client, "lena.vogt")).status_code == 403


def test_diff_between_versions(client) -> None:  # type: ignore[no-untyped-def]
    d = client.get("/api/documents/RL-ZV-01/diff?a=2&b=3", headers=login(client, "lena.vogt")).json()
    changed = {x["tz"]: x for x in d}
    assert "10.000 EUR" in changed["2.1"]["after"] and "15.000 EUR" in changed["2.1"]["before"]
    assert changed["7.2"]["change"] == "added"


def test_personal_data_never_reaches_storage(client, database) -> None:  # type: ignore[no-untyped-def]
    r = ask(
        client,
        "lena.vogt",
        "Kunde mit IBAN DE89370400440532013000 will 20.000 EUR überweisen, ab welchem Betrag Vier-Augen-Prinzip?",
    )
    assert r["trace"]["redacted"] == ["IBAN"]
    with psycopg.connect(database["admin"]) as c:
        stored = c.execute("SELECT question FROM queries WHERE id = %s", (r["query_id"],)).fetchone()[0]
    assert "DE89" not in stored and "[IBAN]" in stored


def test_tokens_and_metrics(client, settings_for_tests) -> None:  # type: ignore[no-untyped-def]
    t = sign("lena.vogt", "test-secret", now=1_000)
    assert verify_token(t, "test-secret", now=1_001) == "lena.vogt"
    assert verify_token(t, "other", now=1_001) is None
    assert verify_token(t, "test-secret", now=1_000 + 9 * 3600) is None
    assert client.post("/api/ask", json={"question": "Hallo Welt?"}).status_code == 401
    assert client.get("/api/metrics").status_code == 401
    m = client.get("/api/metrics", headers={"Authorization": "Bearer scrape"})
    assert m.status_code == 200 and "copilot_answers_total" in m.text
    assert client.post("/api/session", json={"login": "nobody"}).status_code == 401
