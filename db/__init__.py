"""MySQL access for the Apollo scraper.

Credentials are read from the project `.env` (DB_HOST / DB_USER / DB_PASSWORD /
DB_NAME / optional DB_PORT). Never hardcode them.
"""
import os
import mysql.connector
from dotenv import load_dotenv

# .env lives one level up from this package (repo root).
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))


def get_connection():
    """Open a new MySQL connection using the DB_* values from .env."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT", "3306")),
        connection_timeout=15,
    )


def upsert(conn, table, row, key="email"):
    """Insert `row` (a dict of column -> value) into `table`, updating the existing
    row on a duplicate `key`. Relies on a UNIQUE index on `key` (see db/schema.sql).
    Does not commit — the caller controls the transaction.
    """
    cols = list(row.keys())
    col_list = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"`{c}` = VALUES(`{c}`)" for c in cols if c != key)
    sql = (
        f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    cur = conn.cursor()
    cur.execute(sql, [row[c] for c in cols])
    cur.close()
