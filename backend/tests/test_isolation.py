"""The platform must not know the answers: nothing in `copilot` imports the simulation or reads
its test questions."""

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "copilot"


def test_platform_never_imports_the_simulation() -> None:
    offenders = []
    for f in SRC.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        if "copilot_sim" in text or "questions.json" in text or "blind" in text.lower():
            offenders.append(str(f))
    assert offenders == []
