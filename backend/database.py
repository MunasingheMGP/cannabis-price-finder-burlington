"""
PostgreSQL connection pool for cannabis_db.
"""

import psycopg2
from psycopg2 import pool
from contextlib import contextmanager

DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "cannabis_db",
    "user":     "postgres",
    "password": "pgadmin",
}

_pool = pool.SimpleConnectionPool(minconn=1, maxconn=10, **DB_CONFIG)


@contextmanager
def get_connection():
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
