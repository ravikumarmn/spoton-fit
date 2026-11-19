"""Scheduled job: weekly learned maintenance + reviews for every user (PRD P-05).

    python -m spotonfit.jobs.weekly

Run it weekly (e.g. Cloud Scheduler -> Cloud Run Job, Sunday 06:00 local). It's
idempotent: re-running, or users opening the app first, never creates duplicates.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from spotonfit.db import Database, ProfileRow
from spotonfit.observability import setup_logging
from spotonfit.services.progress import generate_weekly

log = logging.getLogger("spotonfit.jobs.weekly")


async def run(db: Database | None = None) -> dict:
    owned = db is None
    db = db or Database()
    try:
        async with db.sessionmaker() as s:
            user_ids = list(await s.scalars(select(ProfileRow.user_id)))
        created = failed = 0
        for uid in user_ids:
            try:
                created += await generate_weekly(db.sessionmaker, uid)
            except Exception:
                failed += 1
                log.exception("weekly generation failed for a user")
        result = {"users": len(user_ids), "reviews_created": created, "failed": failed}
        log.info("weekly job: %s", result)
        return result
    finally:
        if owned:
            await db.dispose()


if __name__ == "__main__":
    setup_logging()
    print(asyncio.run(run()))
