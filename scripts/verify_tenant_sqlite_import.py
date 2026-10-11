from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db.sqlite3"
MEDIA_ROOT = ROOT / "media"

FILE_TOKENS = (
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
SKIP_FILE_COLUMNS = {"original_filename", "file_size", "include_media"}


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def tables(con):
    return [
        row[0]
        for row in con.execute(
            "select name from sqlite_master "
            "where type='table' and name not like 'sqlite_%' "
            "order by name"
        )
    ]


def columns(con, table):
    return [row[1] for row in con.execute(f"pragma table_info({quote(table)})")]


def is_file_column(column):
    lowered = column.lower()
    return lowered not in SKIP_FILE_COLUMNS and any(token in lowered for token in FILE_TOKENS)


def should_check(value):
    if not isinstance(value, str) or not value.strip():
        return False
    lowered = value.lower()
    return not (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("data:")
        or lowered.startswith("/static/")
        or lowered.startswith("static/")
    )


def count(con, sql, params=()):
    return con.execute(sql, params).fetchone()[0]


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    print("tenants")
    for row in con.execute(
        """
        select s.id, s.name, s.slug, group_concat(d.domain, ', ') as domains
        from core_schooltenant s
        left join core_schooldomain d on d.school_id = s.id
        group by s.id, s.name, s.slug
        order by s.id
        """
    ):
        print(f"  {row['id']}: {row['name']} ({row['slug']}) -> {row['domains']}")

    print("counts")
    tenant_rows = con.execute("select id, slug from core_schooltenant order by id").fetchall()
    for row in tenant_rows:
        school_id = row["id"]
        slug = row["slug"]
        print(
            "  "
            + slug
            + ": "
            + ", ".join(
                [
                    f"students={count(con, 'select count(*) from core_student where school_id=?', (school_id,))}",
                    f"teachers={count(con, 'select count(*) from core_teacher where school_id=?', (school_id,))}",
                    f"classes={count(con, 'select count(*) from core_schoolclass where school_id=?', (school_id,))}",
                    f"subjects={count(con, 'select count(*) from core_subject where school_id=?', (school_id,))}",
                    f"memberships={count(con, 'select count(*) from core_schoolmembership where school_id=?', (school_id,))}",
                    f"results={count(con, 'select count(*) from core_result r join core_student st on st.id=r.student_id where st.school_id=?', (school_id,))}",
                    f"quizzes={count(con, 'select count(*) from core_quiz q join core_schoolclass c on c.id=q.school_class_id where c.school_id=?', (school_id,))}",
                    f"website_pages={count(con, 'select count(*) from website_websitepage where school_id=?', (school_id,))}",
                    f"gallery={count(con, 'select count(*) from website_galleryimage where school_id=?', (school_id,))}",
                ]
            )
        )

    missing = []
    checked = 0
    for table in tables(con):
        file_columns = [column for column in columns(con, table) if is_file_column(column)]
        if not file_columns:
            continue
        for column in file_columns:
            for row in con.execute(
                f"select id, {quote(column)} as value from {quote(table)} "
                f"where {quote(column)} is not null and {quote(column)} != ''"
            ):
                value = row["value"]
                if not should_check(value):
                    continue
                checked += 1
                normalized = value.replace("\\", "/").lstrip("/")
                if normalized.startswith("media/"):
                    normalized = normalized[len("media/") :]
                if not (MEDIA_ROOT / normalized).exists():
                    missing.append(f"{table}.{column}#{row['id']} -> {value}")

    fk_errors = con.execute("pragma foreign_key_check").fetchall()
    print(f"media_fields_checked={checked}")
    print(f"missing_media_fields={len(missing)}")
    for item in missing[:20]:
        print(f"  {item}")
    print(f"foreign_key_check_errors={len(fk_errors)}")
    for error in fk_errors[:20]:
        print(f"  {tuple(error)}")
    con.close()


if __name__ == "__main__":
    main()
