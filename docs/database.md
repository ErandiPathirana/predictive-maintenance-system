# Database setup and migrations

SQLAlchemy 2 is used, so the same code runs on **SQLite** (local) and **PostgreSQL** (hosted). The schema is created by **Alembic migrations**.

| Table | Purpose |
|---|---|
| `upload_batches` | One row per CSV upload: id, sanitised filename, record count, time, model version |
| `predictions` | One row per prediction: IDs, `measured_at`, `created_at` (UTC), predicted condition, class id, `scores` (JSON), model version, provenance/demonstration flags, optional `input_readings` |

**Privacy:** raw sensor values are **not stored** unless `STORE_INPUT_READINGS=true`. Logs never contain readings, IDs, filenames or query strings.

## Local (SQLite), from the `backend` folder with the venv active
```powershell
python -m alembic upgrade head        # creates backend\predictions.db with both tables
python -m alembic current             # shows: 0001 (head)
```
`DATABASE_URL=sqlite:///predictions.db` (the default) means the file `backend\predictions.db`. It is git-ignored. To start fresh, stop the server and delete the file, then run `alembic upgrade head` again.

If you start the backend without migrating, it stops with: *database tables are missing. Run 'alembic upgrade head'*.
(`AUTO_CREATE_TABLES=true` skips this for quick local experiments. Do **not** mix it with Alembic on the same database, and it is refused in production.)

## PostgreSQL (hosted)
1. Create a database on your provider. Copy its connection URL (it looks like `postgresql://USER:PASSWORD@HOST:5432/DBNAME`; keep it secret).
2. Install the driver: `pip install -r requirements-postgres.txt`.
3. Set `DATABASE_URL` as an environment variable on the host (never in code or Git). `postgres://` and `postgresql://` are converted automatically for the psycopg 3 driver.
4. Run `python -m alembic upgrade head` once against that database (as a deploy/release step).
> The PostgreSQL path is written to the same SQLAlchemy/Alembic standard but was **not run against a PostgreSQL server** in development. Test it on your host before the viva.

## Changing the schema later
Edit `backend/app/db/models.py`, then `python -m alembic revision --autogenerate -m "describe change"`, review the generated file in `backend/migrations/versions/`, and `python -m alembic upgrade head`. The test `test_migration_creates_exactly_the_model_schema` fails if models and migrations disagree.
