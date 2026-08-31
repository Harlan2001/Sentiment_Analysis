"""Apply the AI strategy history schema migration to the project business database.

This script is a manual, explicit operation and is never called by application startup.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = {
    "up": PROJECT_ROOT / "migrations" / "20260728_ai_strategy_history_up.sql",
    "down": PROJECT_ROOT / "migrations" / "20260728_ai_strategy_history_down.sql",
}


def _connection_settings() -> dict[str, object]:
    required = {
        "host": "MYSQL_HOST",
        "user": "MYSQL_USER",
        "password": "MYSQL_PASSWORD",
        "database": "MYSQL_DATABASE",
    }
    values = {field: os.getenv(variable, "").strip() for field, variable in required.items()}
    missing = [variable for field, variable in required.items() if not values[field]]
    if missing:
        raise RuntimeError("Missing database configuration: " + ", ".join(missing))
    return {
        **values,
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "charset": os.getenv("MYSQL_CHARSET", "utf8mb4").strip() or "utf8mb4",
        "autocommit": False,
    }


def _statements(path: Path) -> list[str]:
    return [statement.strip() for statement in path.read_text(encoding="utf-8").split(";") if statement.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the isolated AI strategy history schema migration")
    parser.add_argument("--rollback", action="store_true", help="Apply the down migration instead")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    direction = "down" if args.rollback else "up"
    with pymysql.connect(**_connection_settings()) as connection:
        with connection.cursor() as cursor:
            for statement in _statements(MIGRATIONS[direction]):
                cursor.execute(statement)
        connection.commit()
    print(f"Applied AI strategy history {direction} migration to the project database.")


if __name__ == "__main__":
    main()
