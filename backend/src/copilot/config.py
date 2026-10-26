"""Settings from the environment and the YAML files in config/ (thresholds never live in code)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COPILOT_", env_file=".env", extra="ignore")

    database_url: str = "postgresql://copilot_app:copilot_app@localhost:5432/copilot"
    admin_database_url: str = "postgresql://postgres:postgres@localhost:5432/copilot"
    app_db_password: str = "copilot_app"
    token_secret: str = "dev-only-secret-change-me"
    config_dir: Path = ROOT / "config"
    cors_origin: str = "http://localhost:5173"
    demo_mode: bool = False
    metrics_token: str | None = None


@dataclass(frozen=True)
class RetrievalConfig:
    candidates_per_path: int
    rrf_k: int
    evidence: int
    min_overlap: float
    history_penalty: float
    section_boost: float
    embedding_dim: int
    unknown_word_weight: float


@dataclass(frozen=True)
class ModelSpec:
    id: str
    provider: str
    model: str
    max_classification: int
    processing: str
    price_in: float
    price_out: float
    enabled_if_env: str | None = None

    @property
    def enabled(self) -> bool:
        return self.enabled_if_env is None or bool(os.environ.get(self.enabled_if_env))


def _yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache
def settings() -> Settings:
    return Settings()


@lru_cache
def retrieval_config(config_dir: Path | None = None) -> RetrievalConfig:
    d = _yaml((config_dir or settings().config_dir) / "retrieval.yaml")
    return RetrievalConfig(**d)


@lru_cache
def models(config_dir: Path | None = None) -> tuple[ModelSpec, ...]:
    d = _yaml((config_dir or settings().config_dir) / "models.yaml")
    return tuple(
        ModelSpec(
            id=m["id"],
            provider=m["provider"],
            model=m["model"],
            max_classification=int(m["max_classification"]),
            processing=m["processing"],
            price_in=float(m["price_per_mtok"]["input"]),
            price_out=float(m["price_per_mtok"]["output"]),
            enabled_if_env=m.get("enabled_if_env"),
        )
        for m in d["models"]
    )


@lru_cache
def thesaurus(config_dir: Path | None = None) -> dict[str, str]:
    d = _yaml((config_dir or settings().config_dir) / "thesaurus.yaml") or {}
    return {str(k).lower(): str(v).lower() for k, v in d.items()}
