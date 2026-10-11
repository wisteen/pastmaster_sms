from pathlib import Path
import shutil
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db.sqlite3"
MEDIA_ROOT = ROOT / "media"


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def copy_missing_dan_signature():
    destination = MEDIA_ROOT / "tenant_imports" / "dan-graciousland-schools" / "school" / "folu.png"
    if destination.exists():
        return False
    candidates = [
        MEDIA_ROOT / "school" / "folu.png",
        MEDIA_ROOT / "signatures" / "teachers" / "folu.png",
        MEDIA_ROOT / "tenant_imports" / "thy-kingdom-come-schools" / "signatures" / "teachers" / "folu.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, destination)
            return True
    return False


def profile_images():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        select school_id, school_logo, school_seal, school_address, school_motto
        from core_schoolsettings
        where school_id is not null
        """
    ).fetchall()
    for row in rows:
        con.execute(
            """
            update website_websiteprofile
            set logo = ?,
                favicon = ?,
                default_og_image = ?,
                address = case when coalesce(address, '') = '' then ? else address end,
                tagline = case when coalesce(tagline, '') = '' then ? else tagline end
            where school_id = ?
            """,
            (
                row["school_logo"] or "",
                row["school_seal"] or "",
                row["school_logo"] or row["school_seal"] or "",
                row["school_address"] or "",
                row["school_motto"] or "",
                row["school_id"],
            ),
        )
    con.commit()
    con.close()
    return len(rows)


if __name__ == "__main__":
    copied = copy_missing_dan_signature()
    updated = profile_images()
    print(f"copied_missing_dan_signature={copied}")
    print(f"updated_profiles={updated}")
