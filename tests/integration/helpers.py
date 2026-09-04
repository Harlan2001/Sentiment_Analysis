"""集成测试造数辅助：在真实测试库上插入业务行。"""

from __future__ import annotations

import uuid


def insert_news(
    conn,
    *,
    source: str = "integration-test",
    title: str = "测试新闻",
    content: str = "本次会议决定适度宽松, 释放流动性。",
    pub_time: str = "2026-09-01 10:00:00",
    **extra,
) -> int:
    """插入一条 news 并返回自增 id。extra 可覆盖/追加字段。"""
    url = extra.pop("url", f"http://test.local/news/{uuid.uuid4().hex}")
    gid = extra.pop("global_uid", uuid.uuid4().hex)
    cols = ["source", "title", "content", "pub_time", "url", "global_uid"]
    vals = [source, title, content, pub_time, url, gid]
    for k, v in extra.items():
        cols.append(k)
        vals.append(v)
    placeholders = ",".join(["%s"] * len(cols))
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO news ({','.join(cols)}) VALUES ({placeholders})", vals
        )
        return cur.lastrowid


def insert_factor(conn, code: str, name: str, category: str = "MACRO") -> int:
    """插入一条因子并返回 id（若 code 已存在则返回既有 id）。"""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM factor WHERE code=%s", (code,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO factor (code, name, category) VALUES (%s, %s, %s)",
            (code, name, category),
        )
        return cur.lastrowid


def insert_user(conn, username: str, password: str = "test-password") -> int:
    """插入一个系统用户并返回 id。"""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, password),
        )
        return cur.lastrowid