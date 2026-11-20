"""Admin: give a locked-out user a temporary password (there is no email reset yet).

    DATABASE_URL=<the database> PYTHONPATH=src .venv/bin/python scripts/reset_password.py someone@example.com

For the live database, get the URL from Secret Manager without printing it:
    DATABASE_URL="$(gcloud secrets versions access latest --secret spotonfit-database-url \\
        --project <your-gcp-project>)" PYTHONPATH=src .venv/bin/python scripts/reset_password.py someone@example.com

Prints a random temporary password and signs the user out everywhere (all refresh tokens
revoked). Send it to them privately; they sign in and change it under Me > Change password.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import secrets
import sys

from sqlalchemy import select, update

from spotonfit.api.security import hash_password
from spotonfit.db import Database, RefreshToken, User


async def reset(db: Database, email: str) -> str:
    password = secrets.token_urlsafe(9)  # 12 characters, above the 8-character minimum
    async with db.sessionmaker() as s:
        user = await s.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            raise LookupError(f"No account for {email}")
        user.password_hash = hash_password(password)
        await s.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=dt.datetime.now(dt.UTC))
        )
        await s.commit()
    return password


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("email")
    args = ap.parse_args()
    db = Database()

    async def run() -> str:
        try:
            return await reset(db, args.email)
        finally:
            await db.dispose()

    try:
        password = asyncio.run(run())
    except LookupError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"Temporary password for {args.email}: {password}")
    print("They are signed out on every device. Share it privately; they change it under Me > Change password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
