"""One-off migration: load the existing Apollo CSVs into the MySQL tables.

Reads the three data CSVs at the repo root and upserts each row (by email) into
the matching table, reusing the shared column coercion in db/__init__.py. Safe
to re-run: it upserts, so rows are updated in place.

    crawler\\Scripts\\python.exe -m db.seed_from_csv
"""
import os
import pandas as pd

from db import get_connection, upsert, coerce_row

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSV_FOR = {
    "apollo_search_data": "apollo_search_data.csv",
    "apollo_credits_data": "apollo_credits_only.csv",
    "apollo_upload_data": "apollo_upload_data_append.csv",
}


def main():
    conn = get_connection()
    for table, csv in CSV_FOR.items():
        path = os.path.join(REPO, csv)
        if not os.path.exists(path):
            print(f"SKIP {table}: {csv} not found")
            continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        n = 0
        for _, r in df.iterrows():
            row = coerce_row(table, r.to_dict())
            if row.get("email") is None:
                continue  # skip rows without the key
            upsert(conn, table, row)
            n += 1
        conn.commit()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        total = cur.fetchone()[0]
        cur.close()
        print(f"{table}: upserted {n} rows from {csv}  (table now has {total})")
    conn.close()
    print("DONE")


if __name__ == "__main__":
    main()
