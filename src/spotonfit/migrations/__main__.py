"""Apply migrations to DATABASE_URL:  python -m spotonfit.migrations
(Used by the deploy pipeline and the Docker image, which has no alembic.ini.)"""

from spotonfit.migrations.runner import upgrade_head

if __name__ == "__main__":
    upgrade_head()
    print("migrations applied (head)")
