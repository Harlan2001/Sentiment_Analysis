"""
数据库连接管理器
仅支持 MySQL 数据库
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import pymysql
from dbutils.pooled_db import PooledDB

# Module-level defaults keep direct imports and diagnostic scripts from failing
# before the FastAPI startup hook creates the connection pool.
_db_config: Optional["DatabaseConfig"] = None
_db_pool: Optional[PooledDB] = None
# 仓储专用池：DictCursor + autocommit=False（面向 repositories/ 与 factor 模块）
_repo_pool: Optional[PooledDB] = None


class DatabaseConfig:
    """MySQL 数据库配置"""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        charset: str = "utf8mb4",
        autocommit: bool = True,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.charset = charset
        self.autocommit = autocommit

    def get_connection_params(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "autocommit"}


def init_database(config: DatabaseConfig, max_connections: int = 50):
    """初始化数据库配置和两个连接池（重建前关闭旧池，避免 mincached 连接泄漏）：
    - 主池：tuple 游标（core 查询/业务代码沿用，conn.cursor() 返回元组行）
    - 仓储池：DictCursor + autocommit=False（面向 repositories/ 与 factor 模块，
      方法内显式 conn.commit()，事务语义与迁移前直连一致）
    """
    global _db_config, _db_pool, _repo_pool
    _db_config = config
    old_pool = _db_pool
    old_repo_pool = _repo_pool
    conn_params = config.get_connection_params()

    _db_pool = PooledDB(
        creator=pymysql,
        maxconnections=max_connections,
        mincached=10,
        maxcached=20,
        ping=1,
        **conn_params,
    )
    _repo_pool = PooledDB(
        creator=pymysql,
        maxconnections=20,
        mincached=2,
        maxcached=10,
        ping=1,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        **conn_params,
    )

    if old_pool is not None:
        try:
            old_pool.close()
        except Exception:
            pass
    if old_repo_pool is not None:
        try:
            old_repo_pool.close()
        except Exception:
            pass


def _ensure_pools() -> None:
    """池未初始化时按环境配置惰性建池（覆盖未调用 init_database() 的入口）。"""
    global _db_config
    if _db_config is None:
        from backend.config.config import MYSQL_CONFIG

        init_database(DatabaseConfig(**MYSQL_CONFIG))


# ====================== 公共连接方法（删除重复逻辑）======================
def _get_raw_connection():
    """底层获取连接（池未初始化时惰性建池）"""
    if _db_pool is None:
        _ensure_pools()
    assert _db_pool is not None
    return _db_pool.connection()


def get_connection_with_retry(max_retries: int = 3):
    """带重试的连接获取（复用底层方法）"""
    last_err = None
    for attempt in range(max_retries):
        try:
            return _get_raw_connection()
        except Exception as e:
            last_err = e
            time.sleep(0.5 * (attempt + 1))
    raise last_err or RuntimeError("数据库连接重试失败")


def get_connection():
    """获取连接（复用方法）"""
    return _get_raw_connection()


# ====================== 上下文管理器（精简重连逻辑）======================
@contextmanager
def get_db_connection(auto_reconnect: bool = True):
    """自动管理数据库连接"""
    conn = None
    try:
        conn = get_connection_with_retry() if auto_reconnect else get_connection()
        yield conn
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ====================== 仓储连接（DictCursor / autocommit=False）======================
def _get_repo_raw_connection():
    """从仓储池获取连接（池未初始化时惰性建池）"""
    if _repo_pool is None:
        _ensure_pools()
    assert _repo_pool is not None
    return _repo_pool.connection()


def _get_repo_connection_with_retry(max_retries: int = 3):
    """带重试的仓储连接获取（复用底层方法）"""
    last_err = None
    for attempt in range(max_retries):
        try:
            return _get_repo_raw_connection()
        except Exception as e:
            last_err = e
            time.sleep(0.5 * (attempt + 1))
    raise last_err or RuntimeError("数据库连接重试失败")


@contextmanager
def get_repo_connection(auto_reconnect: bool = True):
    """管理仓储连接（DictCursor、autocommit=False），exit 时归还连接池。

    事务语义与迁移前的直连一致：写入方法内显式 conn.commit()，
    异常路径由 DBUtils reset 在归还时 rollback 未提交事务。
    """
    conn = None
    try:
        if auto_reconnect:
            conn = _get_repo_connection_with_retry()
        else:
            conn = _get_repo_raw_connection()
        yield conn
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ====================== 统一执行工具（复用游标逻辑）======================
def _execute_helper(conn, query: str, params=None, executemany=False):
    """统一游标执行助手（删除三处重复代码）"""
    with conn.cursor() as cursor:
        if executemany:
            return cursor.executemany(query, params or [])
        return cursor.execute(query, params or ())


def execute_query(query: str, params: Optional[tuple] = None, one: bool = False):
    """执行查询（简化参数，删除冗余逻辑）"""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchone() if one else cursor.fetchall()


def execute_update(query: str, params: Optional[tuple] = None) -> int:
    """执行增删改"""
    with get_db_connection() as conn:
        rows = _execute_helper(conn, query, params)
        conn.commit()
        return rows


def execute_batch(query: str, params_list: List[tuple]) -> int:
    """批量执行"""
    with get_db_connection() as conn:
        rows = _execute_helper(conn, query, params_list, executemany=True)
        conn.commit()
        return rows


def build_in_placeholders(items) -> str:
    """为 SQL ``IN`` 子句生成占位符串（如 3 项 → ``"%s,%s,%s"``）。

    注意：调用方需自行保证 items 非空（空 ``IN ()`` 是非法 SQL）。
    """
    return ",".join(["%s"] * len(items))
