"""HTTP API. Every request that touches documents runs under the caller's row-level security."""

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from ..answer.answerability import AnswerabilityModel
from ..answer.answerers import Answerer, build_answerers
from ..answer.service import ask, verify_chain
from ..config import ModelSpec, RetrievalConfig, Settings, models, retrieval_config, settings, thesaurus
from ..db import Pool as ConnectionPool
from ..db import Principal, as_system, as_user, principal
from ..retrieval.search import load_vocabulary
from ..text import Embedder, SketchEmbedder, Vocabulary

TOKEN_TTL_S = 8 * 3600


def sign(login: str, secret: str, now: float | None = None) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"sub": login, "exp": int((now or time.time()) + TOKEN_TTL_S)}).encode())
    mac = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"{body.decode()}.{mac}"


def verify_token(token: str, secret: str, now: float | None = None) -> str | None:
    try:
        body, mac = token.split(".")
    except ValueError:
        return None
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return None
    data = json.loads(base64.urlsafe_b64decode(body))
    return str(data["sub"]) if data["exp"] > (now or time.time()) else None


@dataclass
class Deps:
    pool: ConnectionPool
    settings: Settings
    cfg: RetrievalConfig
    embedder: Embedder
    thesaurus: dict[str, str]
    specs: tuple[ModelSpec, ...]
    answerers: dict[str, Answerer]
    eval_report: Path | None = None
    vocab: Vocabulary | None = None
    vocab_at: float = 0.0
    registry: CollectorRegistry = field(default_factory=CollectorRegistry)

    def vocabulary(self) -> Vocabulary:
        """Word statistics of the indexed policies, refreshed every ten minutes (new versions)."""
        if self.vocab is None or time.time() - self.vocab_at > 600:
            with as_system(self.pool) as conn:
                self.vocab = load_vocabulary(conn, self.cfg.unknown_word_weight)
            self.vocab_at = time.time()
        return self.vocab


class AskBody(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    as_of: date | None = None


class FeedbackBody(BaseModel):
    helpful: bool
    comment: str = Field(default="", max_length=2000)


class ResolveBody(BaseModel):
    resolution: str = Field(min_length=3, max_length=2000)


class SessionBody(BaseModel):
    login: str


def build_app(deps: Deps) -> FastAPI:
    app = FastAPI(title="Bank policy copilot", version="0.1.0")
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[deps.settings.cors_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    requests = Counter("copilot_http_requests_total", "HTTP requests", ["route", "status"], registry=deps.registry)
    latency = Histogram("copilot_http_seconds", "HTTP latency", ["route"], registry=deps.registry)
    outcomes = Counter(
        "copilot_answers_total", "Answers by outcome and model", ["outcome", "model"], registry=deps.registry
    )

    @app.middleware("http")
    async def metrics(request: Request, call_next: Any) -> Any:
        start = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        requests.labels(path, str(response.status_code)).inc()
        latency.labels(path).observe(time.perf_counter() - start)
        return response

    def current(authorization: Annotated[str | None, Header()] = None) -> Principal:
        token = (authorization or "").removeprefix("Bearer ").strip()
        login = verify_token(token, deps.settings.token_secret) if token else None
        who = principal(deps.pool, login) if login else None
        if who is None:
            raise HTTPException(401, "sign in first")
        return who

    Who = Annotated[Principal, Depends(current)]

    def reviewer(who: Who) -> Principal:
        if not who.reviewer:
            raise HTTPException(403, "for reviewers (Compliance, Internal Audit) only")
        return who

    Reviewer = Annotated[Principal, Depends(reviewer)]

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        with deps.pool.connection() as conn:
            conn.execute("SELECT 1")
        return {"ok": True}

    @app.get("/api/metrics", response_class=PlainTextResponse)
    def metrics_endpoint(authorization: Annotated[str | None, Header()] = None) -> PlainTextResponse:
        want = deps.settings.metrics_token
        if want and authorization != f"Bearer {want}":
            raise HTTPException(401, "metrics need a token")
        return PlainTextResponse(generate_latest(deps.registry).decode(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/api/session")
    def session(body: SessionBody) -> dict[str, Any]:
        # Demo sign-in. Production puts the bank's identity provider (OIDC) in front and maps its
        # subject to the same login; rights always come from the users table.
        if not deps.settings.demo_mode:
            raise HTTPException(404, "sign in through the identity provider")
        who = principal(deps.pool, body.login)
        if who is None:
            raise HTTPException(401, "unknown user")
        return {"token": sign(who.login, deps.settings.token_secret), "user": me(who)}

    @app.get("/api/demo-users")
    def demo_users() -> list[dict[str, Any]]:
        if not deps.settings.demo_mode:
            raise HTTPException(404, "not available")
        with as_system(deps.pool) as conn:
            return list(conn.execute("SELECT login, name, title, clearance FROM users ORDER BY name").fetchall())

    @app.get("/api/me")
    def me(who: Who) -> dict[str, Any]:
        with as_user(deps.pool, who) as conn:
            u = conn.execute(
                "SELECT login, name, title, clearance, groups FROM users WHERE login = %s", (who.login,)
            ).fetchone()
        return {**(u or {}), "reviewer": who.reviewer}

    @app.post("/api/ask")
    def ask_endpoint(body: AskBody, who: Who) -> dict[str, Any]:
        on = body.as_of or date.today()
        with as_user(deps.pool, who) as conn:
            r = ask(
                conn,
                who,
                body.question,
                on,
                cfg=deps.cfg,
                embedder=deps.embedder,
                thesaurus=deps.thesaurus,
                specs=deps.specs,
                answerers=deps.answerers,
                vocab=deps.vocabulary(),
            )
        outcomes.labels(r.outcome, r.model).inc()
        return {
            "query_id": r.query_id,
            "outcome": r.outcome,
            "answer": r.answer,
            "citations": r.citations,
            "newer": r.newer,
            "model": r.model,
            "as_of": r.as_of.isoformat(),
            "trace": r.trace,
        }

    @app.get("/api/history")
    def history(who: Who, limit: int = Query(20, le=100)) -> list[dict[str, Any]]:
        with as_user(deps.pool, who) as conn:
            return list(
                conn.execute(
                    """SELECT q.id, q.at, q.question, q.as_of, q.outcome, q.model, f.helpful
                         FROM queries q LEFT JOIN feedback f ON f.query_id = q.id AND f.login = q.login
                        WHERE q.login = %s ORDER BY q.id DESC LIMIT %s""",
                    (who.login, limit),
                ).fetchall()
            )

    @app.get("/api/queries/{query_id}")
    def query(query_id: int, who: Who) -> dict[str, Any]:
        with as_user(deps.pool, who) as conn:
            q = conn.execute("SELECT * FROM queries WHERE id = %s", (query_id,)).fetchone()
            if not q:
                raise HTTPException(404, "not found")
            cites = conn.execute(
                """SELECT p.id AS paragraph_id, p.doc_key, d.title, p.version, p.tz, p.section, p.text,
                          p.valid_from, p.valid_to, p.classification
                     FROM paragraphs p JOIN documents d ON d.doc_key = p.doc_key WHERE p.id = ANY(%s)""",
                (q["citations"],),
            ).fetchall()
        return {**q, "citations": cites}

    @app.post("/api/queries/{query_id}/feedback")
    def feedback(query_id: int, body: FeedbackBody, who: Who) -> dict[str, Any]:
        with as_user(deps.pool, who) as conn:
            q = conn.execute("SELECT login FROM queries WHERE id = %s", (query_id,)).fetchone()
            if not q or q["login"] != who.login:
                raise HTTPException(404, "not found")
            row = conn.execute(
                """INSERT INTO feedback (query_id, login, helpful, comment) VALUES (%s, %s, %s, %s)
                   ON CONFLICT (query_id, login) DO NOTHING RETURNING id""",
                (query_id, who.login, body.helpful, body.comment),
            ).fetchone()
        if not row:
            raise HTTPException(409, "feedback already given")
        return {"id": row["id"]}

    @app.get("/api/review")
    def review(who: Reviewer, status: str = "open") -> list[dict[str, Any]]:
        with as_user(deps.pool, who) as conn:
            return list(
                conn.execute(
                    """SELECT f.id, f.query_id, f.login, f.helpful, f.comment, f.status, f.resolution, f.created_at,
                              q.question, q.as_of, q.answer, q.outcome, q.model, q.citations
                         FROM feedback f JOIN queries q ON q.id = f.query_id
                        WHERE f.status = %s AND NOT f.helpful ORDER BY f.id DESC""",
                    (status,),
                ).fetchall()
            )

    @app.post("/api/review/{feedback_id}/resolve")
    def resolve(feedback_id: int, body: ResolveBody, who: Reviewer) -> dict[str, Any]:
        with as_user(deps.pool, who) as conn:
            cur = conn.execute(
                """UPDATE feedback SET status = 'resolved', resolution = %s, resolved_at = now()
                    WHERE id = %s AND status = 'open'""",
                (body.resolution, feedback_id),
            )
        if cur.rowcount == 0:
            raise HTTPException(404, "no open feedback with that id")
        return {"ok": True}

    @app.get("/api/documents")
    def documents(who: Who, on: date | None = None) -> list[dict[str, Any]]:
        on = on or date.today()
        with as_user(deps.pool, who) as conn:
            return list(
                conn.execute(
                    """SELECT d.doc_key, d.title, d.kind, d.classification, d.owner,
                              max(v.version) FILTER (WHERE v.valid_from <= %(on)s
                                AND (v.valid_to IS NULL OR v.valid_to > %(on)s)) AS version_on,
                              max(v.version) AS latest_version,
                              json_agg(json_build_object('version', v.version, 'valid_from', v.valid_from,
                                'valid_to', v.valid_to) ORDER BY v.version) AS versions
                         FROM documents d JOIN document_versions v ON v.document_id = d.id
                        GROUP BY d.id ORDER BY d.kind DESC, d.doc_key""",
                    {"on": on},
                ).fetchall()
            )

    @app.get("/api/documents/{doc_key:path}/versions/{version}")
    def document_version(doc_key: str, version: int, who: Who) -> dict[str, Any]:
        with as_user(deps.pool, who) as conn:
            d = conn.execute(
                """SELECT d.doc_key, d.title, d.classification, d.owner, v.version, v.valid_from, v.valid_to
                     FROM documents d JOIN document_versions v ON v.document_id = d.id
                    WHERE d.doc_key = %s AND v.version = %s""",
                (doc_key, version),
            ).fetchone()
            if not d:
                raise HTTPException(404, "not found")
            paras = conn.execute(
                "SELECT id, tz, section, text, is_history FROM paragraphs WHERE doc_key = %s AND version = %s ORDER BY id",
                (doc_key, version),
            ).fetchall()
        return {**d, "paragraphs": paras}

    @app.get("/api/documents/{doc_key:path}/diff")
    def diff(doc_key: str, who: Who, a: int, b: int) -> list[dict[str, Any]]:
        with as_user(deps.pool, who) as conn:
            rows = conn.execute(
                """SELECT coalesce(x.tz, y.tz) AS tz, coalesce(y.section, x.section) AS section,
                          x.text AS before, y.text AS after
                     FROM (SELECT * FROM paragraphs WHERE doc_key = %(d)s AND version = %(a)s) x
                     FULL JOIN (SELECT * FROM paragraphs WHERE doc_key = %(d)s AND version = %(b)s) y ON y.tz = x.tz
                    WHERE x.text_hash IS DISTINCT FROM y.text_hash""",
                {"d": doc_key, "a": a, "b": b},
            ).fetchall()
            if not rows and not conn.execute("SELECT 1 FROM documents WHERE doc_key = %s", (doc_key,)).fetchone():
                raise HTTPException(404, "not found")
        return [
            {**r, "change": "added" if r["before"] is None else "removed" if r["after"] is None else "changed"}
            for r in sorted(rows, key=lambda r: [int(x) for x in r["tz"].split(".")])
        ]

    @app.get("/api/impact")
    def impact(who: Reviewer, status: str | None = None) -> list[dict[str, Any]]:
        with as_user(deps.pool, who) as conn:
            return list(
                conn.execute(
                    """SELECT i.*, p.tz, p.text AS paragraph, p.version, d.title
                         FROM impact_items i JOIN paragraphs p ON p.id = i.paragraph_id
                         JOIN documents d ON d.doc_key = i.doc_key
                        WHERE %(s)s::text IS NULL OR i.status = %(s)s ORDER BY i.status, i.id""",
                    {"s": status},
                ).fetchall()
            )

    @app.post("/api/impact/{item_id}/resolve")
    def resolve_impact(item_id: int, body: ResolveBody, who: Reviewer) -> dict[str, Any]:
        with as_user(deps.pool, who) as conn:
            cur = conn.execute(
                "UPDATE impact_items SET status = 'resolved', note = %s WHERE id = %s AND status = 'open'",
                (body.resolution, item_id),
            )
        if cur.rowcount == 0:
            raise HTTPException(404, "no open item with that id")
        return {"ok": True}

    @app.get("/api/audit/verify")
    def audit(who: Who) -> dict[str, Any]:
        if "audit-all" not in who.groups:
            raise HTTPException(403, "for Internal Audit only")
        with as_system(deps.pool) as conn:
            return verify_chain(conn)

    @app.get("/api/models")
    def model_registry(who: Who) -> list[dict[str, Any]]:
        return [
            {
                "id": s.id,
                "model": s.model,
                "enabled": s.enabled,
                "max_classification": s.max_classification,
                "processing": s.processing,
            }
            for s in deps.specs
        ]

    @app.get("/api/evaluation")
    def evaluation(who: Who) -> dict[str, Any]:
        if deps.eval_report is None or not deps.eval_report.exists():
            raise HTTPException(404, "no evaluation report yet")
        data: dict[str, Any] = json.loads(deps.eval_report.read_text(encoding="utf-8"))
        return data

    return app


def default_deps(pool: ConnectionPool | None = None) -> Deps:
    s = settings()
    cfg = retrieval_config()
    specs = models()
    return Deps(
        pool=pool or _pool(s),
        settings=s,
        cfg=cfg,
        embedder=SketchEmbedder(cfg.embedding_dim),
        thesaurus=thesaurus(),
        specs=specs,
        answerers=build_answerers(specs, cfg, AnswerabilityModel.load(s.config_dir / "answerability.json")),
        eval_report=s.config_dir.parent / "reports" / "evaluation.json",
    )


def _pool(s: Settings) -> ConnectionPool:
    from ..db import create_pool

    return create_pool(s.database_url, 16)


def iter_lines(path: Path) -> Iterator[str]:  # pragma: no cover - helper for scripts
    yield from path.read_text(encoding="utf-8").splitlines()


def create_app() -> FastAPI:
    """Entry point for uvicorn: `uvicorn copilot.api.app:create_app --factory`."""
    s = settings()
    if s.token_secret == "dev-only-secret-change-me" and not s.demo_mode:
        raise RuntimeError("COPILOT_TOKEN_SECRET must be set outside demo mode")
    return build_app(default_deps())
