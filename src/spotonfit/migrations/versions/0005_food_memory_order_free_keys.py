"""food memory: re-key names so word order and punctuation don't matter

"egg, boiled" and "boiled egg" now share one key (core.nutrition.food_key). Rows whose new
keys collide for the same user are merged: the most-used row is kept with the summed use count.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-20
"""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NON_WORD = re.compile(r"[^\w\s]")


def _key(name: str) -> str:
    """Frozen copy of core.nutrition.food_key at this revision (migrations must not change)."""

    def singular(w: str) -> str:
        return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w

    return " ".join(sorted(singular(w) for w in _NON_WORD.sub(" ", name.lower()).split()))


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, user_id, name, times_used FROM food_memory ORDER BY times_used DESC, updated_at DESC")
    ).fetchall()
    keep: dict[tuple, tuple] = {}  # (user_id, new key) -> (id, total uses)
    drop: list = []
    for row_id, user_id, name, used in rows:
        k = (user_id, _key(name))
        if k in keep:
            keep[k] = (keep[k][0], keep[k][1] + (used or 0))
            drop.append(row_id)
        else:
            keep[k] = (row_id, used or 0)
    for row_id in drop:
        conn.execute(sa.text("DELETE FROM food_memory WHERE id = :id"), {"id": row_id})
    for (_user, key), (row_id, used) in keep.items():
        conn.execute(
            sa.text("UPDATE food_memory SET name_key = :k, times_used = :u WHERE id = :id"),
            {"k": key, "u": used, "id": row_id},
        )


def downgrade() -> None:
    # Old keys can be rebuilt from names: lower case, single spaces, last word de-pluralised.
    conn = op.get_bind()
    for row_id, name in conn.execute(sa.text("SELECT id, name FROM food_memory")).fetchall():
        words = name.strip().lower().split()
        if words and len(words[-1]) > 3 and words[-1].endswith("s") and not words[-1].endswith("ss"):
            words[-1] = words[-1][:-1]
        conn.execute(
            sa.text("UPDATE food_memory SET name_key = :k WHERE id = :id"), {"k": " ".join(words), "id": row_id}
        )
