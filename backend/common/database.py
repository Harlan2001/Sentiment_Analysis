"""
数据库连接管理器
仅支持 MySQL 数据库
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import pymysql
from dbutils.pooled_db import PooledDB

# 模块级变量（init_database() 调用前为 None）
_db_config = None
_db_pool = None


# Module-level defaults keep direct imports and diagnostic scripts from failing
# before the FastAPI startup hook creates the connection pool.
_db_config: Optional["DatabaseConfig"] = None
_db_pool: Optional[PooledDB] = None


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
    """初始化数据库配置和连接池"""
    global _db_config, _db_pool
    _db_config = config

    _db_pool = PooledDB(
        creator=pymysql,
        maxconnections=max_connections,
        mincached=10,
        maxcached=20,
        ping=1,
        **config.get_connection_params(),
    )


def get_database_config() -> DatabaseConfig:
    """获取数据库配置"""
    if not _db_config:
        raise RuntimeError("请先调用 init_database() 初始化数据库")
    return _db_config


# ====================== 公共连接方法（删除重复逻辑）======================
def _get_raw_connection():
    """底层获取连接（公共方法，删除重复代码）"""
    if _db_pool:
        return _db_pool.connection()
    return pymysql.connect(**get_database_config().get_connection_params())


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
