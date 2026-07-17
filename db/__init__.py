"""MySQL access for the Apollo scraper.

Credentials come from the project `.env` (DB_HOST / DB_USER / DB_PASSWORD /
DB_NAME, optional DB_PORT) — never hardcode them. This module also owns the
column definitions of the three apollo_* tables and the value coercion used by
both the CSV seeder and the live scraper, so the two stay in sync.
"""
import os
import ast
import json
import math
import mysql.connector
from dotenv import load_dotenv

# .env lives one level up from this package (repo root).
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))


# ---------------------------------------------------------------------------
# connection
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# value coercion (shared by the seeder and the scraper)
# ---------------------------------------------------------------------------
def _blank(v):
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return isinstance(v, str) and v.strip().lower() in ("", "nan")


def as_int(v):
    if _blank(v):
        return None
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def as_dt(v):
    """Accept 'YYYY-MM-DD HH:MM:SS[.ffffff]' strings or datetime objects.
    Blanks become NULL (crucial: '' would fail a DATETIME column in strict mode)."""
    if _blank(v):
        return None
    return v if not isinstance(v, str) else v.strip()


def as_text(v):
    return None if _blank(v) else str(v)


def as_json(v):
    """Store as valid JSON. Accepts a real list/dict, a Python-repr string
    (what the CSV holds), or an already-JSON string."""
    if _blank(v):
        return None
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    s = str(v)
    try:
        return json.dumps(ast.literal_eval(s))  # Python repr -> JSON
    except (ValueError, SyntaxError):
        try:
            json.loads(s)
            return s
        except json.JSONDecodeError:
            return None


_MONTHS = ("first", "second", "third", "fourth", "fifth", "sixth")
_CREDIT_COLS = {f"{o}_month_{k}": as_int for o in _MONTHS for k in ("credits", "provided")}

# column -> converter, per table (also the authoritative column list)
COLUMNS = {
    "apollo_search_data": {
        "email": as_text, "status": as_text, "last_execution": as_dt,
        "used_credits": as_int, "total_credits": as_int, "renews_on": as_dt,
        "saved_titles": as_text, "saved_counts": as_text, "total_saved": as_int,
        "netnew_counts": as_text, "total_netnew": as_int, "failed_reason": as_text,
    },
    "apollo_credits_data": {
        "email": as_text, "status": as_text, "last_execution": as_dt,
        "renewal_date": as_dt, **_CREDIT_COLS,
    },
    "apollo_upload_data": {
        "email": as_text, "data_count": as_int, "last_uploaded": as_dt,
        "status": as_text, "last_execution": as_dt, "monthly_breakdown": as_json,
    },
}


def coerce_row(table, raw):
    """Project a raw dict onto the table's columns, converting each value to the
    right SQL type. Keys missing from `raw` become NULL."""
    return {col: conv(raw.get(col)) for col, conv in COLUMNS[table].items()}


# ---------------------------------------------------------------------------
# writes
# ---------------------------------------------------------------------------
def upsert(conn, table, row, key="email"):
    """INSERT `row` into `table`, updating in place on a duplicate `key`.
    Relies on a UNIQUE index on `key` (see db/schema.sql). Does not commit."""
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


def save_row_safe(table, raw, key="email"):
    """Coerce + upsert one row in its own short-lived connection. Never raises:
    a DB problem prints a warning and returns False so scraping continues."""
    conn = None
    try:
        conn = get_connection()
        upsert(conn, table, coerce_row(table, raw), key)
        conn.commit()
        return True
    except Exception as e:  # noqa: BLE001 - DB writes must never break scraping
        print(f"[DB] upsert into {table} failed (continuing): {e}")
        return False
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
