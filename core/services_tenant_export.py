import csv
import io
import json
import os
import posixpath
import zipfile
from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .models_features import SchoolTenant


EXTRA_TENANT_LOOKUPS = {
    ('website', 'WebsiteSection'): 'page__school',
    ('website', 'WebsiteContentItem'): 'section__page__school',
}

EXCLUDED_MODELS = {
    'core.TenantDataExportRequest',
}


USER_EXPORT_FIELDS = [
    'id',
    'username',
    'first_name',
    'last_name',
    'email',
    'role',
    'extra_roles',
    'phone',
    'is_active',
    'is_staff',
    'is_superuser',
    'date_joined',
    'last_login',
]


def generate_tenant_export(export_request):
    """Generate a tenant-scoped ZIP export and attach it to the request."""

    export_request.status = export_request.STATUS_PROCESSING
    export_request.error_message = ''
    export_request.save(update_fields=['status', 'error_message', 'updated_at'])

    try:
        school = export_request.school
        record_counts = {}
        user_ids = set()
        media_paths = {}
        created_at = timezone.now()

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            manifest = {
                'school': {
                    'id': school.id,
                    'name': school.name,
                    'slug': school.slug,
                    'plan': school.plan,
                    'is_active': school.is_active,
                },
                'generated_at': created_at.isoformat(),
                'include_media': export_request.include_media,
                'tables': {},
            }

            for model, queryset in _tenant_model_querysets(school):
                rows = []
                for obj in queryset.iterator():
                    row, file_fields, related_user_ids = _serialize_instance(obj)
                    rows.append(row)
                    user_ids.update(related_user_ids)
                    media_paths.update(file_fields)

                if not rows:
                    continue

                label = _model_label(model)
                record_counts[label] = len(rows)
                manifest['tables'][label] = len(rows)
                _write_json(archive, label, rows)
                _write_csv(archive, label, rows)

            users = _export_users(user_ids, school)
            if users:
                record_counts['auth.users'] = len(users)
                manifest['tables']['auth.users'] = len(users)
                _write_json(archive, 'auth.users', users)
                _write_csv(archive, 'auth.users', users)

            if export_request.include_media:
                media_count = _write_media_files(archive, media_paths)
                manifest['media_files'] = media_count

            archive.writestr('manifest.json', json.dumps(manifest, indent=2, default=_json_default))

        filename = f"{school.slug or 'school'}-tenant-export-{created_at.strftime('%Y%m%d-%H%M%S')}.zip"
        content = ContentFile(buffer.getvalue())
        export_request.export_file.save(filename, content, save=False)
        export_request.file_size = export_request.export_file.size or len(buffer.getvalue())
        export_request.record_counts = record_counts
        export_request.status = export_request.STATUS_READY
        export_request.approved_at = export_request.approved_at or created_at
        export_request.generated_at = created_at
        export_request.expires_at = created_at + timedelta(days=14)
        export_request.save(update_fields=[
            'export_file',
            'file_size',
            'record_counts',
            'status',
            'approved_at',
            'generated_at',
            'expires_at',
            'updated_at',
        ])
        return export_request
    except Exception as exc:
        export_request.status = export_request.STATUS_FAILED
        export_request.error_message = str(exc)
        export_request.save(update_fields=['status', 'error_message', 'updated_at'])
        raise


def _tenant_model_querysets(school):
    for model in apps.get_models():
        if model._meta.auto_created or model._meta.proxy:
            continue
        if model._meta.app_label not in {'core', 'website'}:
            continue
        if model._meta.label in EXCLUDED_MODELS:
            continue
        if model._meta.label == 'core.User':
            continue

        queryset = _queryset_for_model(model, school)
        if queryset is None:
            continue
        yield model, queryset


def _queryset_for_model(model, school):
    manager = getattr(model, 'all_objects', None) or model._default_manager

    if model is SchoolTenant:
        return manager.filter(pk=school.pk)

    lookup = EXTRA_TENANT_LOOKUPS.get((model._meta.app_label, model.__name__))
    if not lookup:
        lookup = _direct_school_lookup(model)
    if not lookup:
        lookup = getattr(model, 'tenant_filter_path', None)
    if not lookup:
        return None

    if isinstance(lookup, (list, tuple, set)):
        query = Q()
        for path in lookup:
            query |= Q(**{path: school})
        return manager.filter(query).distinct()
    return manager.filter(**{lookup: school}).distinct()


def _direct_school_lookup(model):
    for field in model._meta.fields:
        if field.name == 'school' and getattr(field.remote_field, 'model', None) is SchoolTenant:
            return 'school'
    return None


def _serialize_instance(obj):
    row = {}
    file_fields = {}
    related_user_ids = set()
    user_model = _user_model()

    for field in obj._meta.concrete_fields:
        value = field.value_from_object(obj)
        if isinstance(field, models.FileField):
            file_value = getattr(obj, field.name)
            row[field.name] = file_value.name if file_value else ''
            if file_value:
                file_fields[f'{obj._meta.label_lower}.{obj.pk}.{field.name}'] = file_value
            continue

        if isinstance(field, models.ForeignKey) and field.remote_field.model is user_model and value:
            related_user_ids.add(value)

        row[field.name] = _json_safe(value)

    for field in obj._meta.many_to_many:
        values = list(getattr(obj, field.name).values_list('pk', flat=True))
        row[field.name] = values
        if field.remote_field.model is user_model:
            related_user_ids.update(values)

    return row, file_fields, related_user_ids


def _export_users(user_ids, school):
    if not user_ids:
        return []
    user_ids = set(user_ids).intersection(_tenant_user_ids(school))
    if not user_ids:
        return []
    user_model = _user_model()
    rows = []
    for user in user_model._default_manager.filter(pk__in=user_ids).order_by('id'):
        row = {}
        for field_name in USER_EXPORT_FIELDS:
            row[field_name] = _json_safe(getattr(user, field_name, None))
        rows.append(row)
    return rows


def _tenant_user_ids(school):
    user_ids = set()
    for app_label, model_name, lookup in [
        ('core', 'SchoolMembership', 'school'),
        ('core', 'Student', 'school'),
        ('core', 'Teacher', 'school'),
        ('core', 'Guardian', 'student__school'),
    ]:
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        manager = getattr(model, 'all_objects', None) or model._default_manager
        if model_name == 'Guardian':
            ids = manager.filter(**{lookup: school}, user__isnull=False).values_list('user_id', flat=True)
        else:
            ids = manager.filter(**{lookup: school}).values_list('user_id', flat=True)
        user_ids.update(user_id for user_id in ids if user_id)
    return user_ids


def _write_json(archive, label, rows):
    archive.writestr(f'data/{label}.json', json.dumps(rows, indent=2, default=_json_default))


def _write_csv(archive, label, rows):
    if not rows:
        return
    text_buffer = io.StringIO()
    writer = csv.DictWriter(text_buffer, fieldnames=sorted(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(value) for key, value in row.items()})
    archive.writestr(f'data/{label}.csv', text_buffer.getvalue())


def _write_media_files(archive, media_paths):
    written = set()
    count = 0
    for key, file_value in media_paths.items():
        if not file_value or not file_value.name or file_value.name in written:
            continue
        try:
            with file_value.storage.open(file_value.name, 'rb') as source:
                filename = posixpath.join('media', _safe_archive_path(file_value.name))
                archive.writestr(filename, source.read())
                written.add(file_value.name)
                count += 1
        except Exception:
            continue
    return count


def _model_label(model):
    return f'{model._meta.app_label}.{model.__name__}'


def _user_model():
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    return apps.get_model(app_label, model_name)


def _safe_archive_path(path):
    normalized = path.replace('\\', '/').lstrip('/')
    parts = [part for part in normalized.split('/') if part not in {'', '.', '..'}]
    return posixpath.join(*parts) if parts else os.path.basename(normalized)


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _csv_value(value):
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, default=_json_default)
    return '' if value is None else value
