"""
数据库连接管理器。
与原后端一致，仅支持 MySQL 数据库。
"""

from contextlib import contextmanager
from typing import Any, Dict, Optional

import pymysql
from dbutils.pooled_db import PooledDB


_db_config: Optional["DatabaseConfig"] = None
_db_pool: Optional[PooledDB] = None


class DatabaseConfig:
    """MySQL 数据库配置。"""

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
        return {key: value for key, value in self.__dict__.items() if key != "autocommit"}


def init_database(config: DatabaseConfig, max_connections: int = 20):
    """初始化数据库配置和连接池。"""
    global _db_config, _db_pool
    _db_config = config
    _db_pool = PooledDB(
        creator=pymysql,
        maxconnections=max_connections,
        mincached=2,
        maxcached=10,
        ping=1,
        **config.get_connection_params(),
    )


def get_database_config() -> DatabaseConfig:
    if not _db_config:
        raise RuntimeError("请先调用 init_database() 初始化数据库")
    return _db_config


def get_connection():
    if _db_pool:
        return _db_pool.connection()
    return pymysql.connect(**get_database_config().get_connection_params())


@contextmanager
def get_db_connection():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

