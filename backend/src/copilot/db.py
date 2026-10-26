"""Connections. Every unit of work runs as a user (row-level security) or as the system."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool


@dataclass(frozen=True)
class Principal:
    login: str
    clearance: int
    groups: tuple[str, ...]

    @property
    def reviewer(self) -> bool:
        return bool({"copilot-reviewer", "audit-all"} & set(self.groups))


Conn = psycopg.Connection[DictRow]
Pool = ConnectionPool[Conn]


def _configure(conn: Conn) -> None:
    register_vector(conn)


def create_pool(url: str, size: int = 10) -> Pool:
    pool: Pool = ConnectionPool(
        url,
        min_size=1,
        max_size=size,
        kwargs={"row_factory": dict_row},
        configure=_configure,
        open=True,
    )
    pool.wait()
    return pool


@contextmanager
def as_user(pool: Pool, p: Principal) -> Iterator[Conn]:
    """A transaction in which Postgres shows only what this user may read.

    The settings are transaction-local (set_config(..., true)), so a pooled connection never
    carries one user's rights into the next request.
    """
    with pool.connection() as conn, conn.transaction():
        conn.execute(
            "SELECT set_config('app.login', %s, true), set_config('app.clearance', %s, true),"
            " set_config('app.groups', %s, true)",
            (p.login, str(p.clearance), ",".join(p.groups)),
        )
        yield conn


@contextmanager
def as_system(pool: Pool) -> Iterator[Conn]:
    with pool.connection() as conn, conn.transaction():
        conn.execute("SELECT set_config('app.system', 'on', true)")
        yield conn


def principal(pool: Pool, login: str) -> Principal | None:
    """Rights come from the users table (fed by the identity provider), never from the token."""
    with as_system(pool) as conn:
        row = conn.execute("SELECT login, clearance, groups FROM users WHERE login = %s", (login,)).fetchone()
    if not row:
        return None
    return Principal(row["login"], row["clearance"], tuple(row["groups"]))
