# Dan-Gracious website seed

This seed replaces the six public CMS pages for the Dan-Gracious tenant with
curated content and bundled public images supplied for the school.

It updates:

- the public school name, motto, address, phone and email;
- the public website profile, logo, favicon and social preview image;
- Home, About, Academics, Admissions, Gallery and School Fees pages;
- the principal and proprietor/director profiles, portraits and messages;
- eight public campus/activity gallery images; and
- three public school-fee FAQs.

It does not read the legacy HTML at runtime. It does not update students,
student photographs, users, results, attendance, inquiries, subscribers,
payments or financial ledger records.

## Before running on cPanel

1. Deploy the latest project, including `website/seed_assets/dan_gracious/`.
2. Back up the production database and the site's media directory.
3. Activate the same Python virtual environment used by the cPanel app.
4. Change into the directory containing `manage.py`.
5. Run pending migrations:

   ```bash
   python manage.py migrate
   ```

## Preview the target

The production tenant slug is expected to be `dan-graciousland-schools`.
Preview without changing anything:

```bash
python manage.py seed_dan_gracious_website --dry-run
```

If the cPanel tenant uses a different slug, list tenants and pass the correct
one explicitly:

```bash
python manage.py seed_tenant_website --list
python manage.py seed_dan_gracious_website --school-slug YOUR-SLUG --dry-run
```

## Apply the seed

```bash
python manage.py seed_dan_gracious_website
```

Or with an explicit tenant:

```bash
python manage.py seed_dan_gracious_website --school-slug dan-graciousland-schools
```

The command is repeatable. Re-running it refreshes the six seeded CMS pages
without duplicating pages, leadership profiles, curated gallery positions or
FAQs. It replaces the sections inside those six public pages, so take a backup
first if staff have manually edited those pages in Django admin.

## Optional text-only run

If media storage is temporarily unavailable, update the records without
copying bundled images:

```bash
python manage.py seed_dan_gracious_website --skip-images
```

Run the normal command later to install the images.

## After running

1. Open the school domain and verify Home, About, Academics, Admissions,
   Gallery and School Fees.
2. Confirm that the principal portrait is shown with Pastor Juliet Olele and
   the director portrait with Mrs Okorafor Peace Ngozika.
3. Confirm the fee and FCMB account information with the school before making
   it public for a new session. The seeded page clearly identifies the supplied
   returning-student figure as 1st Term 2025/2026.
4. Restart the cPanel Python application if Passenger caches the old process.

No `collectstatic` command is required for these photographs; the seed copies
them into Django media storage. The web server must already be configured to
serve `MEDIA_ROOT` at `MEDIA_URL`.
