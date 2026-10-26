"""python -m copilot_sim export <folder> | seed <folder> | evaluate [--sets dev,blind]"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from copilot.config import retrieval_config, settings
from copilot.db import as_system, create_pool
from copilot.ingest.pipeline import ingest_export
from copilot.migrate import migrate
from copilot.text import SketchEmbedder

from .evaluate import evaluate
from .render import export
from .world import World

ROOT = Path(__file__).resolve().parents[3]
REPORTS = Path(os.environ.get("COPILOT_REPORTS_DIR", ROOT / "reports"))


def gate(report: dict) -> list[str]:  # type: ignore[type-arg]
    """The release bar: nothing leaks, ever; the blind set gives no more wrong answers than on its
    first run; the development questions stay above 90 %."""
    problems = []
    for name, s in report["sets"].items():
        if s["leaks"]:
            problems.append(f"{name}: {s['leaks']} leaks")
    first = report.get("first_runs", {}).get("blind")
    blind = report["sets"].get("blind")
    if first and blind and blind["wrong_answers"] > first["wrong_answers"]:
        problems.append(f"blind: {blind['wrong_answers']} wrong answers, first run had {first['wrong_answers']}")
    dev = report["sets"].get("dev")
    if dev and dev["accuracy"] < 0.9:
        problems.append(f"dev accuracy {dev['accuracy']} below 0.9")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(prog="copilot_sim")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("export", "seed"):
        p = sub.add_parser(name)
        p.add_argument("folder", type=Path, nargs="?", default=ROOT / "data" / "export")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--sets", default="dev,regression-v1,blind")
    sub.add_parser("gate", help="fail if the latest evaluation got worse than the release bar")
    tr = sub.add_parser("train-answerability")
    tr.add_argument("--max-wrong-rate", type=float, default=0.02)
    args = ap.parse_args()
    s = settings()
    if args.cmd in ("export", "seed"):
        listing = export(World(), args.folder)
        print(f"exported {len(listing)} files to {args.folder}")
        if args.cmd == "seed":
            migrate(s.admin_database_url, s.app_db_password)
            pool = create_pool(s.database_url, 2)
            with as_system(pool) as conn:
                report = ingest_export(conn, args.folder, SketchEmbedder(retrieval_config().embedding_dim))
            print(json.dumps(report.__dict__, ensure_ascii=False))
            pool.close()
    elif args.cmd == "gate":
        problems = gate(json.loads((REPORTS / "evaluation.json").read_text(encoding="utf-8")))
        for p in problems:
            print(f"GATE: {p}")
        raise SystemExit(1 if problems else 0)
    elif args.cmd == "train-answerability":
        from .train import train

        pool = create_pool(s.database_url, 4)
        out = train(pool, s.config_dir, max_wrong_rate=args.max_wrong_rate)
        print(json.dumps({k: out[k] for k in ("threshold", "cross_validation", "trained_on", "version")}, indent=2))
        pool.close()
    else:
        pool = create_pool(s.database_url, 4)
        results = evaluate(pool, REPORTS, tuple(args.sets.split(",")))
        for name, r in results["sets"].items():
            print(
                f"{name}: accuracy {r['accuracy']}, answers {r['answer_accuracy']}, recall {r['retrieval_recall']}, "
                f"declined {r['declined_correctly']}, wrong answers {r['wrong_answers']}, leaks {r['leaks']}, "
                f"p50 {r['latency_ms_p50']} ms"
            )
        pool.close()


if __name__ == "__main__":
    main()
