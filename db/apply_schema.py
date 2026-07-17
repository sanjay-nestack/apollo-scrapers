"""Create/verify the Apollo tables by applying db/schema.sql (idempotent).

    crawler\\Scripts\\python.exe -m db.apply_schema
"""
import os

from db import get_connection

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def main():
    sql = open(SCHEMA, encoding="utf-8").read()
    # drop full-line comments, then split into statements
    body = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    statements = [s.strip() for s in body.split(";") if s.strip()]

    conn = get_connection()
    cur = conn.cursor()
    for s in statements:
        cur.execute(s)
        print("OK:", s.split("(")[0].strip().replace("\n", " ")[:70])
    conn.commit()
    cur.close()
    conn.close()
    print("schema applied")


if __name__ == "__main__":
    main()
