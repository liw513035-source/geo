from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.config import settings


def connect() -> psycopg.Connection:
    return psycopg.connect(
        settings.database_url,
        row_factory=dict_row,
        options="-c search_path=geo",
    )


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
