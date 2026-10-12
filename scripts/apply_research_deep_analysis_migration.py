"""Apply the research-report deep-analysis schema migration (sql/015).

Additive-only migration for the business database:
  report_generation_tasks: + version_no, + parent_task_id  (task version chain)
  research_report:         + ai_deep_markdown              (板块一深度拆解)

Idempotent: columns that already exist are skipped. Manual, explicit operation;
never called by application startup.
"""

from __future__ import annotations

import os

import pymysql
from dotenv import load_dotenv

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

NEW_COLUMNS = {
    "report_generation_tasks": ("version_no", "parent_task_id"),
    "research_report": ("ai_deep_markdown",),
}

ALTERS = {
    "report_generation_tasks": (
        "ADD COLUMN version_no int(11) NOT NULL DEFAULT 1 "
        "COMMENT '版本号，再生成递增' AFTER source_snapshot_json, "
        "ADD COLUMN parent_task_id char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci "
        "DEFAULT NULL COMMENT '再生成来源任务' AFTER version_no"
    ),
    "research_report": (
        "ADD COLUMN ai_deep_markdown mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci "
        "DEFAULT NULL COMMENT '深度拆解 Markdown（板块一）' AFTER ai_evidence"
    ),
}


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    database = os.getenv("MYSQL_DATABASE", "").strip()
    if not database:
        raise RuntimeError("MYSQL_DATABASE is not configured")
    if database.endswith("_test"):
        raise RuntimeError("Refusing to run a business migration against a *_test database")

    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=database,
        charset="utf8mb4",
        connect_timeout=10,
        autocommit=False,
    )
    try:
        with conn.cursor() as cursor:
            for table, columns in NEW_COLUMNS.items():
                placeholders = ", ".join(["%s"] * len(columns))
                cursor.execute(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_schema=%s AND table_name=%s "
                    f"AND column_name IN ({placeholders})",
                    (database, table, *columns),
                )
                present = {row[0] for row in cursor.fetchall()}
                missing = [column for column in columns if column not in present]
                if not missing:
                    print(f"[skip] {table}: all new columns already exist")
                    continue
                if present:
                    raise RuntimeError(
                        f"{table} has a partial column set (present={sorted(present)}, "
                        f"missing={missing}); inspect the table manually before continuing"
                    )
                cursor.execute(f"ALTER TABLE `{table}` {ALTERS[table]}")
                print(f"[ok] {table}: added {', '.join(columns)}")
        conn.commit()

        with conn.cursor() as cursor:
            for table, columns in NEW_COLUMNS.items():
                placeholders = ", ".join(["%s"] * len(columns))
                cursor.execute(
                    f"SELECT column_name, column_type FROM information_schema.columns "
                    f"WHERE table_schema=%s AND table_name=%s "
                    f"AND column_name IN ({placeholders})",
                    (database, table, *columns),
                )
                for name, column_type in cursor.fetchall():
                    print(f"[verified] {table}.{name} {column_type}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
