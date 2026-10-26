"""copilot migrate | ingest <export folder> | serve"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import retrieval_config, settings
from .db import as_system, create_pool
from .ingest.pipeline import ingest_export
from .migrate import migrate
from .text import SketchEmbedder


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="copilot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    ing = sub.add_parser("ingest")
    ing.add_argument("folder", type=Path)
    srv = sub.add_parser("serve")
    srv.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)
    s = settings()
    if args.cmd == "migrate":
        print("applied:", ", ".join(migrate(s.admin_database_url, s.app_db_password)) or "nothing new")
    elif args.cmd == "ingest":
        migrate(s.admin_database_url, s.app_db_password)
        pool = create_pool(s.database_url, 2)
        with as_system(pool) as conn:
            report = ingest_export(conn, args.folder, SketchEmbedder(retrieval_config().embedding_dim))
        print(json.dumps(report.__dict__, indent=2, ensure_ascii=False))
        pool.close()
    elif args.cmd == "serve":
        import uvicorn

        uvicorn.run("copilot.api.app:create_app", factory=True, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
