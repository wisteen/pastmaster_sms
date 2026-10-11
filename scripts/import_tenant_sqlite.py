from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
import json
import shutil
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
TARGET_DB = ROOT / "db.sqlite3"
TARGET_MEDIA_ROOT = ROOT / "media"

SCHOOLS = [
    {
        "key": "thy",
        "name": "Thy Kingdom Come Schools",
        "slug": "thy-kingdom-come-schools",
        "domains": ["http://thykingdomcomeschools.com.ng"],
        "source_db": ROOT.parent / "thy_kingdom_come" / "db.sqlite3",
        "source_media": ROOT.parent / "thy_kingdom_come" / "media" / "media",
    },
    {
        "key": "dan",
        "name": "Dan-Graciousland Schools",
        "slug": "dan-graciousland-schools",
        "domains": ["https://dan-graciouslandschools.com"],
        "source_db": ROOT.parent / "Dan-gracious" / "db.sqlite3",
        "source_media": ROOT.parent / "Dan-gracious" / "media" / "media",
    },
]

RETAIN_TARGET_TABLES = {
    "django_migrations",
    "django_content_type",
    "auth_permission",
    "django_site",
}

SKIP_SOURCE_TABLES = {
    "django_migrations",
    "django_content_type",
    "auth_permission",
    "django_admin_log",
    "django_session",
    "django_site",
    "core_schooltenant",
    "core_schooldomain",
    "core_schoolmembership",
    "website_websiteprofile",
    "website_websitepage",
    "website_websitesection",
    "website_websitecontentitem",
    "website_websiteteammember",
}

ROLE_CHOICES = {
    "student",
    "parent",
    "subject_teacher",
    "class_teacher",
    "librarian",
    "accountant",
    "bursar",
    "security",
    "super_admin",
}

FILE_COLUMN_TOKENS = (
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

SPECIAL_DEFAULTS = {
    ("core_user", "extra_roles"): "[]",
    ("core_student", "gender"): "M",
    ("core_student", "status"): "active",
    ("core_student", "archived_at"): None,
    ("core_student", "archive_note"): "",
    ("core_teacher", "signature"): "",
    ("core_subject", "subject_type"): "academic",
    ("core_term", "session"): "2024-2025",
    ("core_term", "vacation_date"): None,
    ("core_term", "resumption_date"): None,
    ("core_term", "school_opened_days"): 0,
    ("core_classteacher", "can_assign_parent_wards"): 0,
    ("core_classteacher", "can_print_download_results"): 0,
    ("core_payrolldeduction", "loan_id"): None,
    ("core_reportcardsettings", "third_term_mode"): "cumulative",
    ("core_reportcardsettings", "template"): "classic",
    ("core_reportcardsettings", "class_templates"): "{}",
    ("core_reportcardsettings", "signatories"): "[]",
    ("core_reportcardsettings", "domain_rating_guide"): "[]",
    ("core_reportcardsettings", "class_domain_rating_guides"): "{}",
    ("core_schoolsettings", "primary_color"): "#0f766e",
    ("core_schoolsettings", "secondary_color"): "#1d4ed8",
    ("core_schoolsettings", "accent_color"): "#f59e0b",
    ("core_schoolsettings", "back_home_url"): "",
    ("core_schoolsettings", "email_from_address"): "",
    ("core_schoolsettings", "email_host"): "",
    ("core_schoolsettings", "email_port"): 587,
    ("core_schoolsettings", "email_host_user"): "",
    ("core_schoolsettings", "email_host_password"): "",
    ("core_schoolsettings", "email_use_tls"): 1,
    ("core_schoolsettings", "termii_api_key"): "",
    ("core_schoolsettings", "termii_base_url"): "https://api.ng.termii.com",
    ("core_schoolsettings", "termii_sender_id"): "",
    ("core_schoolsettings", "termii_channel"): "dnd",
    ("core_schoolsettings", "promotion_min_average"): 50,
    ("core_schoolsettings", "promotion_max_failed_subjects"): 2,
    ("core_schoolsettings", "promotion_min_attendance"): 75,
    ("core_schoolmembership", "extra_roles"): "[]",
    ("core_schoolmembership", "portal_access_enabled"): 1,
    ("core_schoolmembership", "result_access_enabled"): 1,
}

GENERIC_OBJECT_TABLES = {
    ("core", "student"): "core_student",
    ("core", "teacher"): "core_teacher",
}

AUDIT_OBJECT_TABLES = {
    "fee_structure": "core_feestructure",
    "student_fee": "core_studentfee",
    "fee_payment": "core_feepayment",
    "scholarship": "core_scholarship",
    "scholarship_recipient": "core_scholarshiprecipient",
    "staff_payroll": "core_staffpayroll",
    "financial_transaction": "core_financialtransaction",
    "payroll_structure": "core_payrollstructure",
}


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def now_value() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")


def table_names(con: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in con.execute(
            "select name from sqlite_master "
            "where type='table' and name not like 'sqlite_%' "
            "order by name"
        )
    ]


def columns(con: sqlite3.Connection, table: str) -> list[dict]:
    return [
        {
            "cid": row[0],
            "name": row[1],
            "type": (row[2] or "").upper(),
            "notnull": bool(row[3]),
            "default": row[4],
            "pk": bool(row[5]),
        }
        for row in con.execute(f"pragma table_info({quote(table)})")
    ]


def column_names(con: sqlite3.Connection, table: str) -> list[str]:
    return [column["name"] for column in columns(con, table)]


def fk_by_column(con: sqlite3.Connection, table: str) -> dict[str, str]:
    return {
        row[3]: row[2]
        for row in con.execute(f"pragma foreign_key_list({quote(table)})")
    }


def max_id(con: sqlite3.Connection, table: str) -> int:
    names = column_names(con, table)
    if "id" not in names:
        return 0
    return con.execute(f"select coalesce(max(id), 0) from {quote(table)}").fetchone()[0] or 0


def parse_sqlite_default(value):
    if value is None:
        return None
    raw = str(value).strip()
    upper = raw.upper()
    if upper == "NULL":
        return None
    if upper in {"CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME"}:
        return now_value()
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        return raw[1:-1].replace("''", "'")
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def default_for(table: str, column: dict):
    key = (table, column["name"])
    if key in SPECIAL_DEFAULTS:
        return SPECIAL_DEFAULTS[key]
    if column["default"] is not None:
        return parse_sqlite_default(column["default"])
    if not column["notnull"]:
        return None
    col_type = column["type"]
    name = column["name"].lower()
    if "date" in name or "time" in name:
        return now_value()
    if "INT" in col_type or "BOOL" in col_type:
        return 0
    if any(token in col_type for token in ("REAL", "FLOA", "DOUB", "DEC", "NUM")):
        return 0
    if "TEXT" in col_type or "CHAR" in col_type:
        return ""
    return None


def clean_domain(value: str) -> str:
    parsed = urlparse(value)
    host = parsed.netloc or parsed.path
    return host.split("/")[0].split(":")[0].lower()


def file_column(name: str) -> bool:
    lowered = name.lower()
    if lowered in {"original_filename", "file_size", "include_media"}:
        return False
    return any(token in lowered for token in FILE_COLUMN_TOKENS)


def normalize_media_path(value: str) -> str:
    path = value.replace("\\", "/").strip()
    while path.startswith("/"):
        path = path[1:]
    while path.startswith("media/"):
        path = path[len("media/") :]
    return path


def should_rewrite_media(value) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    return not (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("data:")
        or stripped.startswith("/static/")
        or stripped.startswith("static/")
    )


def rewrite_media_path(value, school: dict, missing_media: list[str]):
    if not should_rewrite_media(value):
        return value
    normalized = normalize_media_path(value)
    source_path = school["source_media"] / normalized
    if not source_path.exists():
        missing_media.append(f"{school['key']}:{normalized}")
    return f"tenant_imports/{school['slug']}/{normalized}"


def copy_media_tree(school: dict) -> tuple[int, int]:
    source_root = school["source_media"]
    target_root = TARGET_MEDIA_ROOT / "tenant_imports" / school["slug"]
    if not source_root.exists():
        return 0, 0
    files = 0
    bytes_copied = 0
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        destination = target_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        files += 1
        bytes_copied += source.stat().st_size
    return files, bytes_copied


def backup_target() -> Path:
    if not TARGET_DB.exists():
        raise SystemExit(f"Target SQLite database does not exist: {TARGET_DB}")
    backup = TARGET_DB.with_suffix(
        f".pre_tenant_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    )
    shutil.copy2(TARGET_DB, backup)
    return backup


def clear_target(con: sqlite3.Connection) -> None:
    con.execute("pragma foreign_keys = off")
    for table in table_names(con):
        if table in RETAIN_TARGET_TABLES:
            continue
        con.execute(f"delete from {quote(table)}")
    con.commit()


def make_content_type_map(source: sqlite3.Connection, target: sqlite3.Connection):
    source_rows = source.execute(
        "select id, app_label, model from django_content_type"
    ).fetchall()
    target_rows = target.execute(
        "select id, app_label, model from django_content_type"
    ).fetchall()
    target_by_key = {(row["app_label"], row["model"]): row["id"] for row in target_rows}
    source_to_target = {}
    source_to_key = {}
    for row in source_rows:
        key = (row["app_label"], row["model"])
        source_to_key[row["id"]] = key
        if key in target_by_key:
            source_to_target[row["id"]] = target_by_key[key]
    return source_to_target, source_to_key


def make_permission_map(source: sqlite3.Connection, target: sqlite3.Connection, source_ct_to_key):
    target_rows = target.execute(
        """
        select p.id, p.codename, c.app_label, c.model
        from auth_permission p
        join django_content_type c on c.id = p.content_type_id
        """
    ).fetchall()
    target_by_key = {
        (row["app_label"], row["model"], row["codename"]): row["id"]
        for row in target_rows
    }
    source_rows = source.execute(
        "select id, codename, content_type_id from auth_permission"
    ).fetchall()
    permission_map = {}
    for row in source_rows:
        ct_key = source_ct_to_key.get(row["content_type_id"])
        if not ct_key:
            continue
        key = (ct_key[0], ct_key[1], row["codename"])
        if key in target_by_key:
            permission_map[row["id"]] = target_by_key[key]
    return permission_map


def normalize_role(role: str, is_superuser: int = 0) -> str:
    if role in ROLE_CHOICES:
        return role
    return "super_admin" if is_superuser else "student"


def make_unique_username(username, school: dict, user_id: int, existing: set[str]) -> str:
    base = (username or f"user_{school['slug']}_{user_id}").strip() or f"user_{school['slug']}_{user_id}"
    candidate = base[:150]
    if candidate.lower() not in existing:
        existing.add(candidate.lower())
        return candidate

    suffix = "_" + school["slug"].replace("-", "_")
    limit = 150 - len(suffix)
    candidate = f"{base[:limit]}{suffix}"
    counter = 2
    while candidate.lower() in existing:
        counter_suffix = f"{suffix}_{counter}"
        limit = 150 - len(counter_suffix)
        candidate = f"{base[:limit]}{counter_suffix}"
        counter += 1
    existing.add(candidate.lower())
    return candidate


def build_id_maps(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    source_tables: set[str],
    target_tables: set[str],
):
    id_maps = {}
    import_tables = sorted((source_tables & target_tables) - SKIP_SOURCE_TABLES)
    for table in import_tables:
        target_cols = column_names(target, table)
        source_cols = column_names(source, table)
        if "id" not in target_cols or "id" not in source_cols:
            continue
        offset = max_id(target, table)
        old_ids = [
            row[0]
            for row in source.execute(f"select id from {quote(table)} order by id")
        ]
        id_maps[table] = {old_id: old_id + offset for old_id in old_ids}
    return import_tables, id_maps


def prepare_value(
    table: str,
    column: dict,
    row: sqlite3.Row,
    source_columns: set[str],
    school: dict,
    tenant_id: int,
    id_maps: dict,
    existing_usernames: set[str],
    missing_media: list[str],
):
    name = column["name"]
    if name == "id" and "id" in source_columns:
        return id_maps.get(table, {}).get(row["id"], row["id"])
    if name == "school_id":
        return tenant_id
    if table == "core_user" and name == "username":
        return make_unique_username(row["username"], school, row["id"], existing_usernames)
    if table == "core_user" and name == "role":
        return normalize_role(row["role"], row["is_superuser"])
    if name in source_columns:
        value = row[name]
    else:
        value = default_for(table, column)
    if file_column(name):
        value = rewrite_media_path(value, school, missing_media)
    return value


def remap_foreign_keys(
    table: str,
    values: dict,
    row: sqlite3.Row,
    source_columns: set[str],
    target_fks: dict[str, str],
    id_maps: dict,
    ct_map: dict,
    permission_map: dict,
    source_ct_to_key: dict,
    skipped_fk: list[str],
) -> bool:
    for column, ref_table in target_fks.items():
        if column == "school_id" or column not in values:
            continue
        old_value = row[column] if column in source_columns else values[column]
        if old_value in (None, ""):
            continue
        if ref_table == "django_content_type":
            mapped = ct_map.get(old_value)
        elif ref_table == "auth_permission":
            mapped = permission_map.get(old_value)
        elif ref_table in id_maps:
            mapped = id_maps[ref_table].get(old_value)
        else:
            mapped = old_value
        if mapped is None:
            skipped_fk.append(f"{table}.{column}->{ref_table}:{old_value}")
            return False
        values[column] = mapped

    if table == "core_bookborrowing":
        old_ct = row["borrower_content_type_id"] if "borrower_content_type_id" in source_columns else None
        old_object_id = row["borrower_object_id"] if "borrower_object_id" in source_columns else None
        if old_ct and old_object_id:
            object_table = GENERIC_OBJECT_TABLES.get(source_ct_to_key.get(old_ct))
            if object_table in id_maps:
                values["borrower_object_id"] = id_maps[object_table].get(old_object_id)
    if table == "core_financialauditlog":
        object_table = AUDIT_OBJECT_TABLES.get(values.get("model_name"))
        old_object_id = row["object_id"] if "object_id" in source_columns else None
        if object_table in id_maps and old_object_id:
            values["object_id"] = id_maps[object_table].get(old_object_id, old_object_id)
    return True


def insert_row(con: sqlite3.Connection, table: str, values: dict) -> None:
    names = list(values)
    placeholders = ", ".join("?" for _ in names)
    sql = (
        f"insert into {quote(table)} "
        f"({', '.join(quote(name) for name in names)}) "
        f"values ({placeholders})"
    )
    con.execute(sql, [values[name] for name in names])


def create_tenant(con: sqlite3.Connection, school: dict) -> int:
    tenant_id = max_id(con, "core_schooltenant") + 1
    stamp = now_value()
    con.execute(
        """
        insert into core_schooltenant
        (id, name, slug, plan, is_active, contact_name, contact_email, contact_phone, created_at, updated_at)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tenant_id,
            school["name"],
            school["slug"],
            "premium",
            1,
            "",
            "",
            "",
            stamp,
            stamp,
        ),
    )
    for domain in school["domains"]:
        con.execute(
            """
            insert into core_schooldomain
            (domain, is_primary, created_at, school_id)
            values (?, ?, ?, ?)
            """,
            (clean_domain(domain), 1, stamp, tenant_id),
        )
    return tenant_id


def create_system_license(con: sqlite3.Connection, school: dict, tenant_id: int) -> None:
    existing = con.execute(
        "select count(*) from core_systemlicense where school_id = ?", (tenant_id,)
    ).fetchone()[0]
    if existing:
        return
    license_id = max_id(con, "core_systemlicense") + 1
    today = datetime.utcnow().date()
    expiry = today + timedelta(days=365)
    con.execute(
        """
        insert into core_systemlicense
        (id, school_name, license_key, activation_date, expiry_date, is_active,
         grace_period_days, contact_email, contact_phone, admin_message,
         created_at, updated_at, school_id)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            license_id,
            school["name"],
            f"{school['slug'].upper()}-TRIAL",
            today.isoformat(),
            expiry.isoformat(),
            1,
            7,
            "",
            "",
            "",
            now_value(),
            now_value(),
            tenant_id,
        ),
    )


def create_memberships(
    target: sqlite3.Connection,
    source: sqlite3.Connection,
    school: dict,
    tenant_id: int,
    user_map: dict[int, int],
) -> int:
    if not user_map:
        return 0
    target_cols = {column["name"] for column in columns(target, "core_schoolmembership")}
    count = 0
    for row in source.execute("select id, role, is_superuser from core_user order by id"):
        user_id = user_map.get(row["id"])
        if not user_id:
            continue
        membership_id = max_id(target, "core_schoolmembership") + 1
        stamp = now_value()
        values = {
            "id": membership_id,
            "primary_role": normalize_role(row["role"], row["is_superuser"]),
            "extra_roles": "[]",
            "is_active": 1,
            "created_at": stamp,
            "updated_at": stamp,
            "school_id": tenant_id,
            "user_id": user_id,
        }
        if "portal_access_enabled" in target_cols:
            values["portal_access_enabled"] = 1
        if "result_access_enabled" in target_cols:
            values["result_access_enabled"] = 1
        insert_row(target, "core_schoolmembership", values)
        count += 1
    return count


def import_school(
    target: sqlite3.Connection,
    school: dict,
    existing_usernames: set[str],
    target_tables: set[str],
    target_metadata: dict[str, list[dict]],
    target_fks: dict[str, dict[str, str]],
) -> dict:
    source = sqlite3.connect(school["source_db"])
    source.row_factory = sqlite3.Row
    source_tables = set(table_names(source))
    import_tables, id_maps = build_id_maps(source, target, source_tables, target_tables)
    ct_map, source_ct_to_key = make_content_type_map(source, target)
    permission_map = make_permission_map(source, target, source_ct_to_key)
    tenant_id = create_tenant(target, school)
    media_files, media_bytes = copy_media_tree(school)

    summary = {
        "tenant_id": tenant_id,
        "tables": defaultdict(int),
        "skipped_tables": {},
        "skipped_rows": defaultdict(int),
        "missing_media": [],
        "skipped_fk": [],
        "media_files": media_files,
        "media_bytes": media_bytes,
    }

    for table in sorted(source_tables - target_tables):
        count = source.execute(f"select count(*) from {quote(table)}").fetchone()[0]
        if count:
            summary["skipped_tables"][table] = count

    for table in import_tables:
        target_cols = target_metadata[table]
        source_cols_list = column_names(source, table)
        source_cols = set(source_cols_list)
        rows = source.execute(f"select * from {quote(table)} order by rowid").fetchall()
        for row in rows:
            values = {
                column["name"]: prepare_value(
                    table,
                    column,
                    row,
                    source_cols,
                    school,
                    tenant_id,
                    id_maps,
                    existing_usernames,
                    summary["missing_media"],
                )
                for column in target_cols
            }
            if not remap_foreign_keys(
                table,
                values,
                row,
                source_cols,
                target_fks.get(table, {}),
                id_maps,
                ct_map,
                permission_map,
                source_ct_to_key,
                summary["skipped_fk"],
            ):
                summary["skipped_rows"][table] += 1
                continue
            try:
                insert_row(target, table, values)
                summary["tables"][table] += 1
            except sqlite3.IntegrityError as exc:
                summary["skipped_rows"][table] += 1
                summary["skipped_fk"].append(f"{table}: integrity error: {exc}")

    summary["memberships"] = create_memberships(
        target,
        source,
        school,
        tenant_id,
        id_maps.get("core_user", {}),
    )
    create_system_license(target, school, tenant_id)
    source.close()
    return summary


def reset_sequences(con: sqlite3.Connection) -> None:
    sequence_exists = con.execute(
        "select count(*) from sqlite_master where type='table' and name='sqlite_sequence'"
    ).fetchone()[0]
    if not sequence_exists:
        return
    for table in table_names(con):
        if "id" not in column_names(con, table):
            continue
        max_value = max_id(con, table)
        existing = con.execute(
            "select count(*) from sqlite_sequence where name = ?", (table,)
        ).fetchone()[0]
        if existing:
            con.execute("update sqlite_sequence set seq = ? where name = ?", (max_value, table))
        else:
            con.execute("insert into sqlite_sequence (name, seq) values (?, ?)", (table, max_value))


def print_summary(backup: Path, summaries: dict[str, dict], fk_errors: list[sqlite3.Row]) -> None:
    print(f"Backup: {backup}")
    for school in SCHOOLS:
        summary = summaries[school["key"]]
        print(f"\n{school['name']} ({school['slug']})")
        print(f"  tenant_id: {summary['tenant_id']}")
        print(f"  media copied: {summary['media_files']} files, {summary['media_bytes']} bytes")
        print(f"  memberships: {summary['memberships']}")
        important = [
            "core_user",
            "core_student",
            "core_teacher",
            "core_schoolclass",
            "core_subject",
            "core_term",
            "core_result",
            "core_quiz",
            "core_questionbank",
            "core_question",
            "core_quizattempt",
            "core_quizanswer",
            "website_galleryimage",
        ]
        for table in important:
            if summary["tables"].get(table):
                print(f"  {table}: {summary['tables'][table]}")
        if summary["skipped_tables"]:
            print(f"  skipped legacy tables: {dict(summary['skipped_tables'])}")
        if summary["skipped_rows"]:
            print(f"  skipped rows: {dict(summary['skipped_rows'])}")
        if summary["missing_media"]:
            print(f"  missing referenced media: {len(summary['missing_media'])}")
            for item in summary["missing_media"][:20]:
                print(f"    {item}")
        if summary["skipped_fk"]:
            print(f"  row notes: {len(summary['skipped_fk'])}")
            for item in summary["skipped_fk"][:20]:
                print(f"    {item}")
    print(f"\nforeign_key_check errors: {len(fk_errors)}")
    for error in fk_errors[:20]:
        print(f"  {tuple(error)}")


def main() -> None:
    TARGET_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    for school in SCHOOLS:
        if not school["source_db"].exists():
            raise SystemExit(f"Missing source database: {school['source_db']}")
    backup = backup_target()
    target = sqlite3.connect(TARGET_DB)
    target.row_factory = sqlite3.Row
    target.execute("pragma foreign_keys = off")
    clear_target(target)

    target_tables = set(table_names(target))
    target_metadata = {table: columns(target, table) for table in target_tables}
    target_fks = {table: fk_by_column(target, table) for table in target_tables}
    existing_usernames = {
        row[0].lower()
        for row in target.execute("select username from core_user where username != ''")
    }

    summaries = {}
    try:
        for school in SCHOOLS:
            summaries[school["key"]] = import_school(
                target,
                school,
                existing_usernames,
                target_tables,
                target_metadata,
                target_fks,
            )
        reset_sequences(target)
        target.commit()
        target.execute("pragma foreign_keys = on")
        fk_errors = target.execute("pragma foreign_key_check").fetchall()
        print_summary(backup, summaries, fk_errors)
        if fk_errors:
            raise SystemExit("Foreign key check failed; restore the backup before converting.")
    except Exception:
        target.rollback()
        raise
    finally:
        target.close()


if __name__ == "__main__":
    main()
