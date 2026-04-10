# Checklist App API

FastAPI backend boilerplate for milestone 1.

## What is included

- Modular FastAPI app structure under `app/`
- Config and logging bootstrap in `app/core/`
- API router composition in `app/api/router.py`
- Placeholder routes for milestone 1 seams:
	- `GET /api/v1/health`
	- `POST /api/v1/auth/login` (501 placeholder)
	- `POST /api/v1/payments/stripe/webhook` (501 placeholder)
- Test scaffold in `tests/`
- Access window helper in `app/services/access.py`

## Prerequisites

- Python 3.11+
- Existing virtual environment at `apps/api/venv`

## Local setup (existing venv)

From `apps/api`:

```bash
./venv/bin/python --version
./venv/bin/pip install -e '.[test]'
```

## Run the API

From `apps/api`:

```bash
./venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Run tests

From `apps/api`:

```bash
./venv/bin/pytest
```

## Environment variables

Copy `.env.example` to `.env` and adjust values if needed:

```bash
cp .env.example .env
```

Current settings are loaded by `app/core/config.py`.

