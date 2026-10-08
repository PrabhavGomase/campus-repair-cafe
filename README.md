# Campus Repair Café

A Django and PostgreSQL application for campus repair requests, volunteer assignments, donated spare parts, and measurable reuse. The project is designed for the BCSE302P Database Systems Lab assessment. The core database has **10 application tables**; Django adds its own authentication, session, and migration tables.

## Features

- Requester registration, login, and logout; coordinator and volunteer roles in the same `User` table.
- Request creation, editing, cancellation, assignment, repair sessions, completion, and feedback.
- Spare-part donations and usage with atomic stock updates that reject insufficient stock.
- Search, status filtering, pagination, responsive screens, role-limited pages and JSON API.
- PostgreSQL status audit trigger, completion stored procedure, `repair_summary` view, indexes, joins, and aggregate reports.
- Argon2 password hashing when dependencies are installed, Django CSRF protection, ORM queries, and environment-based secrets.

## Technology

Python 3.14, Django 6.1.2, PostgreSQL 17, Django ORM, HTML/CSS, Docker, GitHub Actions. SQLite is available for a quick local demo, but PostgreSQL is needed to demonstrate the stored procedure and trigger.

## Quick start on Windows

Use the existing virtual environment, or create a new one:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a new `DJANGO_SECRET_KEY` and database password in `.env`. Django does not read `.env` automatically in this project: set the values in the shell, or use the Docker Compose setup below. To run a SQLite demo with your existing environment, the default settings work without PostgreSQL:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. A superuser acts as coordinator. In `/admin/`, add an item category, create a volunteer account (`role=volunteer`), and optionally add spare parts. Public registration creates requester accounts only.

## Full PostgreSQL setup with Docker

Copy `.env.example` to `.env`, replace the example secrets, and set `DJANGO_DEBUG=0` only when serving behind HTTPS. For local Docker testing keep `DJANGO_DEBUG=1`.

```powershell
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py test
```

Open `http://localhost:8000/`. `docker compose down` stops services while retaining the database volume. Use `docker compose down -v` only when you intend to erase database data.

## Demonstration flow

1. Coordinator creates a category and a volunteer in Django admin.
2. Requester registers and submits a repair request.
3. Coordinator assigns the volunteer.
4. Coordinator records a donated part; volunteer records a repair session and uses the part.
5. Volunteer completes the repair; requester leaves feedback.
6. Coordinator opens Reports and inspects the database view with `SELECT * FROM repair_summary;`.

The `repair_summary` view and PostgreSQL procedure/trigger are installed by migration `0002_database_features.py`. Status changes are audited automatically by the PostgreSQL trigger. SQLite uses the application service to record status history because SQLite has no stored procedures.

## Tests

```powershell
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

GitHub Actions runs migrations, tests, and a deployment settings check on pushes and pull requests. The test suite checks role isolation, registration privilege safety, stock transactions, and repair completion.

## Backup and restore

For Docker PostgreSQL, use `scripts/backup.ps1` and `scripts/restore.ps1`. Practice restoration on a disposable database before using it for a real deployment. Never commit dumps or `.env`; `.gitignore` excludes them.

## Deployment checklist

1. Create a private GitHub repository and keep `main` and `dev` branches. Make meaningful commits as work progresses; do not invent historical commits.
2. Set `DJANGO_DEBUG=0`, a unique secret key, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS` on the host. Use HTTPS and a managed PostgreSQL database.
3. Install dependencies, run `python manage.py migrate`, `python manage.py collectstatic --noinput`, and `python manage.py check --deploy`.
4. Launch with `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` on Linux. Configure host health checks and backups.
5. Build and push a Docker image to your Docker Hub account. Add the live URL and screenshots to the final report after deployment.

The earlier Django starter secret key was committed before this code replaced it. Never use that key for deployment; set a fresh secret through the environment.

## Assessment documents

See `docs/proposal.md`, `docs/er-diagram.md`, `docs/relational-schema.md`, `docs/data-dictionary.md`, and `docs/timeline.md`. Add real timestamped screenshots to `docs/screenshots/` after running the application. Replace proposal placeholders with your actual name, registration number, slot, and team responsibilities.
