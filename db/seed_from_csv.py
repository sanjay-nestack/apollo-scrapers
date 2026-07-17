"""One-off migration: load the existing Apollo CSVs into the MySQL tables.

Reads the three data CSVs at the repo root and upserts each row (by email) into
the matching table. Safe to re-run: it upserts, so rows are updated in place.

    crawler\\Scripts\\python.exe -m db.seed_from_csv
"""
import os
import ast
import json
import pandas as pd

from db import get_connection, upsert

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---- value converters -------------------------------------------------------
def _blank(v):
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return str(v).strip() == "" or str(v).strip().lower() == "nan"


def as_int(v):
    if _blank(v):
        return None
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def as_dt(v):
    # MySQL accepts 'YYYY-MM-DD HH:MM:SS[.ffffff]'. Blanks -> NULL.
    return None if _blank(v) else str(v).strip()


def as_text(v):
    return None if _blank(v) else str(v)


def as_json(v):
    """CSV stores monthly_breakdown as a Python repr (single quotes). Convert to
    valid JSON so it lands in the JSON column."""
    if _blank(v):
        return None
    s = str(v)
    try:
        return json.dumps(ast.literal_eval(s))
    except (ValueError, SyntaxError):
        try:  # maybe it is already valid JSON
            json.loads(s)
            return s
        except json.JSONDecodeError:
            return None


# ---- per-table column -> converter -----------------------------------------
INT6 = {f"{o}_month_{k}": as_int
        for o in ("first", "second", "third", "fourth", "fifth", "sixth")
        for k in ("credits", "provided")}

TABLES = {
    "apollo_search_data": {
        "csv": "apollo_search_data.csv",
        "cols": {
            "email": as_text, "status": as_text, "last_execution": as_dt,
            "used_credits": as_int, "total_credits": as_int, "renews_on": as_dt,
            "saved_titles": as_text, "saved_counts": as_text, "total_saved": as_int,
            "netnew_counts": as_text, "total_netnew": as_int, "failed_reason": as_text,
        },
    },
    "apollo_credits_data": {
        "csv": "apollo_credits_only.csv",
        "cols": {
            "email": as_text, "status": as_text, "last_execution": as_dt,
            "renewal_date": as_dt, **INT6,
        },
    },
    "apollo_upload_data": {
        "csv": "apollo_upload_data_append.csv",
        "cols": {
            "email": as_text, "data_count": as_int, "last_uploaded": as_dt,
            "status": as_text, "last_execution": as_dt, "monthly_breakdown": as_json,
        },
    },
}


def main():
    conn = get_connection()
    for table, spec in TABLES.items():
        path = os.path.join(REPO, spec["csv"])
        if not os.path.exists(path):
            print(f"SKIP {table}: {spec['csv']} not found")
            continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        n = 0
        for _, r in df.iterrows():
            row = {col: conv(r.get(col)) for col, conv in spec["cols"].items()}
            if _blank(row.get("email")):
                continue  # skip rows without a key
            upsert(conn, table, row)
            n += 1
        conn.commit()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        total = cur.fetchone()[0]
        cur.close()
        print(f"{table}: upserted {n} rows from {spec['csv']}  (table now has {total})")
    conn.close()
    print("DONE")


if __name__ == "__main__":
    main()
