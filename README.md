# Carwaan

Django REST API for the Carwaan ride-sharing backend.

## Local setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy the environment template and replace the placeholders:

   ```bash
   cp .env.example .env
   ```

   Set at least:

   - `SECRET_KEY` — a long random string. Generate one with:
     `python -c "import secrets; print(secrets.token_urlsafe(50))"`
   - `DEBUG=True` for local work only. The application default is `False`.
   - `ALLOWED_HOSTS` — comma-separated hosts such as `localhost,127.0.0.1`. A wildcard is rejected when `DEBUG` is false.
   - `CORS_ALLOWED_ORIGINS` — comma-separated origins such as `http://localhost:8000,http://127.0.0.1:8000`. `CORS_ALLOW_ALL_ORIGINS` stays `False` unless you explicitly enable it for local debug.
   - `ADMIN_PASSWORD` and `TEST_USER_PASSWORD` if you will create seed or admin accounts.

   SQLite is the local database and needs no password. To use PostgreSQL, set `DB_ENGINE=django.db.backends.postgresql` and fill in `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`.

   Email and map/OAuth keys are optional. Leave them blank until you need those features.

3. Apply migrations and start the server:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

   The admin site is at `http://127.0.0.1:8000/admin/`.

## Seed data

These commands read passwords from the environment. They do not contain passwords in source.

```bash
python manage.py populate_quick_data
python manage.py create_test_users
python manage.py update_admin --create-superuser
```

`populate_test_data` and `export_user_credentials` can write a CSV of account passwords. Those files are gitignored. Do not commit them.

## Secrets

`.env` is gitignored. Do not commit it, service-account JSON, OAuth client files, or credential CSVs.

Passwords and keys that were committed before this cleanup are still in git history. Change those account passwords and rotate `SECRET_KEY`, database passwords, email passwords, and API keys. Removing them from the current tree does not invalidate copies that were already cloned.
