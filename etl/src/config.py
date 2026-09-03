"""Loading of runtime configuration from the environment.

The ETL and the API share the same PostgreSQL database, so it reads the very
same ``DATABASE_URL`` that the API uses. Credentials come from ``.env`` and are
never hard-coded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Prefer explicit ETL variables but fall back to the API's DATABASE_URL so the
# two components stay on the same database out of the box.
_DEFAULT_URL = (
    "postgresql://postgres:postgres@localhost:5432/order_inventory"
)


@dataclass(frozen=True)
class Settings:
    database_url: str


def load_settings() -> Settings:
    load_dotenv()  # looks for `.env` in cwd and parents

    url = (
        os.getenv("ETL_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or _DEFAULT_URL
    )
    return Settings(database_url=url)
