"""Fixtures: a fresh database with the simulated bank's export ingested (for the `db` tests)."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg_pool import ConnectionPool

from copilot.config import Settings, models, retrieval_config, thesaurus
from copilot.db import as_system, create_pool
from copilot.ingest.pipeline import ingest_export
from copilot.migrate import migrate
from copilot.text import SketchEmbedder
from copilot_sim.render import export
from copilot_sim.world import World

ADMIN = os.environ.get("COPILOT_TEST_ADMIN_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
DB = "copilot_test"


def _url(base: str, db: str, user: str | None = None, password: str | None = None) -> str:
    from urllib.parse import urlsplit, urlunsplit

    u = urlsplit(base)
    netloc = u.netloc
    if user:
        host = netloc.split("@")[-1]
        netloc = f"{user}:{password}@{host}"
    return urlunsplit((u.scheme, netloc, f"/{db}", u.query, u.fragment))


@pytest.fixture(scope="session")
def export_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("export")
    export(World(), out)
    return out


@pytest.fixture(scope="session")
def database(export_dir: Path) -> Iterator[dict[str, str]]:
    try:
        with psycopg.connect(ADMIN, autocommit=True, connect_timeout=3) as c:
            c.execute(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
            c.execute(f"CREATE DATABASE {DB}")
    except psycopg.OperationalError as e:  # pragma: no cover
        pytest.skip(f"no PostgreSQL for db tests: {e}")
    admin = _url(ADMIN, DB)
    app = _url(ADMIN, DB, "copilot_app", "copilot_app")
    migrate(admin, "copilot_app")
    pool = create_pool(app, 2)
    with as_system(pool) as conn:
        ingest_export(conn, export_dir, SketchEmbedder(retrieval_config().embedding_dim))
    pool.close()
    yield {"admin": admin, "app": app}


@pytest.fixture(scope="session")
def pool(database: dict[str, str]) -> Iterator[ConnectionPool]:
    p = create_pool(database["app"], 6)
    yield p
    p.close()


@pytest.fixture(scope="session")
def settings_for_tests(database: dict[str, str]) -> Settings:
    return Settings(
        database_url=database["app"],
        admin_database_url=database["admin"],
        token_secret="test-secret",
        demo_mode=True,
        metrics_token="scrape",
    )


@pytest.fixture(scope="session")
def client(pool: ConnectionPool, settings_for_tests: Settings):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from copilot.answer.answerability import AnswerabilityModel
    from copilot.answer.answerers import build_answerers
    from copilot.api.app import Deps, build_app
    from copilot.retrieval.search import load_vocabulary

    cfg = retrieval_config()
    specs = models()
    with as_system(pool) as conn:
        vocab = load_vocabulary(conn, cfg.unknown_word_weight)
    deps = Deps(
        pool=pool,
        settings=settings_for_tests,
        cfg=cfg,
        embedder=SketchEmbedder(cfg.embedding_dim),
        thesaurus=thesaurus(),
        specs=specs,
        answerers=build_answerers(
            specs, cfg, AnswerabilityModel.load(settings_for_tests.config_dir / "answerability.json")
        ),
        vocab=vocab,
        vocab_at=time.time(),
    )
    return TestClient(build_app(deps))


def login(client, who: str) -> dict[str, str]:  # type: ignore[no-untyped-def]
    r = client.post("/api/session", json={"login": who})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
