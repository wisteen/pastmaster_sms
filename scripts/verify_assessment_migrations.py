"""Validate the pending assessment migration chain on a copy of local SQLite data."""
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')

from django.conf import settings

database = settings.DATABASES['default']
if database['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('This verification script only supports a local SQLite database.')

source = Path(database['NAME']).resolve()
if source.parent != PROJECT or not source.is_file():
    raise SystemExit('The source database must exist in this project directory.')
target = PROJECT / f'db.assessment_validation_{datetime.now():%Y%m%d_%H%M%S}.sqlite3'
if target.exists():
    raise SystemExit('The validation database already exists; refusing to overwrite it.')

def existing_grades(connection):
    return {
        'assignments': connection.execute('SELECT id, score, feedback, submitted_at FROM core_assignmentsubmission ORDER BY id').fetchall(),
        'quizzes': connection.execute('SELECT id, auto_score, manual_score, final_score, is_submitted FROM core_quizattempt ORDER BY id').fetchall(),
    }

with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original:
    before = existing_grades(original)
    with sqlite3.connect(target) as copied:
        original.backup(copied)

# Override the default database before Django starts. Legacy data migrations
# use the default alias, so a secondary alias would not isolate all writes.
database['NAME'] = str(target)

import django
django.setup()
from django.core.management import call_command
from django.db import connection

assert Path(connection.settings_dict['NAME']).resolve() == target
call_command('migrate', 'core', '0073_assessment_submission_integrity', interactive=False)
call_command('check')
connection.close()

with sqlite3.connect(target) as migrated:
    assert migrated.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
    assert not migrated.execute('PRAGMA foreign_key_check').fetchall()
    assert existing_grades(migrated) == before, 'Existing submission grades changed.'
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original:
    assert existing_grades(original) == before, 'The source database changed.'

print(f'Validated database copy: {target}')
print('Existing assignment grades and quiz results preserved; source database unchanged.')
