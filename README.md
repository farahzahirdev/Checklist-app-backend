# Checklist App API

FastAPI backend for the Checklist App platform.

## What this app is about

This service provides the backend API for authentication, payments, access lifecycle, and checklist workflows. It is designed as a modular REST API so public pages and the authenticated frontend can integrate through a single API boundary.

## How it works

- `app/main.py` boots FastAPI and mounts the versioned API router.
- `app/api/router.py` combines route modules into `/api/v1`.
- Route handlers validate data through schemas and delegate logic to services.
- Services hold business rules such as access-window calculation.
- Tests call the API with `TestClient` to verify endpoint behavior.

## Backend structure

- `app/main.py`: app startup and router wiring.
- `app/api/`: route modules and API composition.
- `app/core/`: settings and logging configuration.
- `app/schemas/`: request and response models.
- `app/services/`: domain logic helpers.
- `tests/`: API and service tests.

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

