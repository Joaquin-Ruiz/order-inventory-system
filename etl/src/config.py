"""Loading of runtime configuration from the environment.

The ETL and the API share the same PostgreSQL database, so it reads the very
same ``DATABASE_URL`` that the API uses. Credentials come from ``.env`` and are
never hard-coded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    database_url: str


def load_settings() -> Settings:
    load_dotenv()  # looks for `.env` in cwd and parents

    url = os.getenv("ETL_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "ETL_DATABASE_URL or DATABASE_URL must be defined"
        )
    return Settings(database_url=url)
