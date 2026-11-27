"""Seed the paper-review Skill into the isolated local MySQL test container."""

from __future__ import annotations

import os
from pathlib import Path

import pymysql
from pymysql.constants import CLIENT

ROOT = Path(__file__).resolve().parent.parent
SKILL_SQL = ROOT / "sql" / "031_strategy_paper_skill.sql"


def main() -> None:
    host = os.getenv("MYSQL_HOST", "")
    port = os.getenv("MYSQL_PORT", "")
    database = os.getenv("MYSQL_DATABASE", "")
    if (
        os.getenv("PYTHON_DOTENV_DISABLED") != "1"
        or host != "127.0.0.1"
        or port != "3307"
        or database != "Sentiment_analysis_test"
    ):
        raise SystemExit(
            "拒绝执行：仅允许 PYTHON_DOTENV_DISABLED=1 且目标为 "
            "127.0.0.1:3307/Sentiment_analysis_test"
        )

    connection = pymysql.connect(
        host=host,
        port=int(port),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=database,
        charset="utf8mb4",
        client_flag=CLIENT.MULTI_STATEMENTS,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(SKILL_SQL.read_text(encoding="utf-8"))
            while cursor.nextset():
                pass
        connection.commit()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM workbench_skills WHERE id = %s",
                ("00000000-0000-4000-8000-000000000109",),
            )
            row = cursor.fetchone()
        if not row or row[0] != "金融论文审阅":
            raise SystemExit("Skill 名称校验失败，请检查 SQL 文件编码")
        print("Seeded financial paper review Skill in local test database")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
