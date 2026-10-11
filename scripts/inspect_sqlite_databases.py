from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
DATABASES = [
    ("target", ROOT / "db.sqlite3"),
    ("thy", ROOT.parent / "thy_kingdom_come" / "db.sqlite3"),
    ("dan", ROOT.parent / "Dan-gracious" / "db.sqlite3"),
]


def table_names(cursor):
    return [
        row[0]
        for row in cursor.execute(
            "select name from sqlite_master "
            "where type='table' and name not like 'sqlite_%' "
            "order by name"
        )
    ]


def quote(name):
    return '"' + name.replace('"', '""') + '"'


for label, path in DATABASES:
    print(f"\nDB {label}: {path}")
    if not path.exists():
        print("missing")
        continue
    con = sqlite3.connect(path)
    cur = con.cursor()
    tables = table_names(cur)
    print(f"tables: {len(tables)}")
    for table in tables:
        count = cur.execute(f"select count(*) from {quote(table)}").fetchone()[0]
        columns = [row[1] for row in cur.execute(f"pragma table_info({quote(table)})")]
        shown = ",".join(columns[:14])
        if len(columns) > 14:
            shown += ",..."
        print(f"{table}: {count}: {shown}")
    print("media samples:")
    for table in tables:
        columns = [row[1] for row in cur.execute(f"pragma table_info({quote(table)})")]
        file_columns = [
            column
            for column in columns
            if any(
                token in column.lower()
                for token in (
                    "photo",
                    "logo",
                    "seal",
                    "signature",
                    "image",
                    "file",
                    "attachment",
                    "document",
                    "certificate",
                    "id_card",
                )
            )
        ]
        if not file_columns:
            continue
        where = " or ".join(f"{quote(column)} != ''" for column in file_columns)
        rows = cur.execute(
            f"select {', '.join(quote(column) for column in file_columns)} "
            f"from {quote(table)} where {where} limit 3"
        ).fetchall()
        if rows:
            print(f"  {table}: {file_columns}: {rows}")
    con.close()
