import os
from pathlib import Path
from functools import lru_cache
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Please create a .env file first."
        )

    return database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = get_database_url()
    engine = create_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
    )
    return engine


def get_conn() -> Connection:
    """
    兼容旧代码的数据库连接入口。

    旧脚本可能会调用：
        conn = get_conn()
        conn.close()

    新代码推荐直接使用：
        get_engine().connect()
        get_engine().begin()
    """

    return get_engine().connect()


def normalize_value(value: Any) -> Any:
    """
    将数据库返回的特殊类型转换成更适合前端和 Agent 使用的类型。
    Decimal -> float
    datetime/date -> isoformat string
    list/dict -> 递归转换
    """

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()

    if isinstance(value, dict):
        return {k: normalize_value(v) for k, v in value.items()}

    if isinstance(value, list):
        return [normalize_value(v) for v in value]

    return value


def normalize_row(row: dict) -> dict:
    return {k: normalize_value(v) for k, v in row.items()}


def execute_sql_file(sql_file_path: str | Path) -> None:
    sql_file_path = Path(sql_file_path)

    if not sql_file_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_file_path}")

    sql = sql_file_path.read_text(encoding="utf-8")

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql))


def fetch_all(sql: str, params: dict | None = None) -> list[dict]:
    engine = get_engine()

    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        rows = result.mappings().all()

    return [normalize_row(dict(row)) for row in rows]


def fetch_one(sql: str, params: dict | None = None) -> dict | None:
    engine = get_engine()

    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        row = result.mappings().first()

    return normalize_row(dict(row)) if row else None


def execute_write(sql: str, params: dict | None = None) -> int:
    engine = get_engine()

    with engine.begin() as conn:
        result = conn.execute(text(sql), params or {})

    return result.rowcount
