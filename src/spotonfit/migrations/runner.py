"""Run Alembic programmatically (used by dev startup and the deploy pipeline).

CLI equivalent from the repo root:  uv run alembic upgrade head
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR = Path(__file__).resolve().parent


def alembic_config(url: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    if url:
        cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))  # ConfigParser escaping
    return cfg


def upgrade_head(url: str | None = None) -> None:
    command.upgrade(alembic_config(url), "head")
