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

Interactive API docs (Swagger UI):

- http://localhost:8000/docs
- http://localhost:8000/redoc

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

## Database and migrations

This API now includes a PostgreSQL ORM layer (SQLAlchemy 2.0) and Alembic migrations.

Development defaults (already in `.env.example`):

- `DB_HOST=localhost`
- `DB_PORT=5432`
- `DB_NAME=ckecklist`
- `DB_USER=postgres`
- `DB_PASSWORD=password`

Run migrations from `apps/api`:

```bash
./venv/bin/alembic upgrade head
```

Create a new migration after model changes:

```bash
./venv/bin/alembic revision --autogenerate -m "describe_change"
```

## API modules and behavior

### Health

- `GET /api/v1/health`
- Purpose: liveness probe for monitoring and uptime checks.

### Auth

- `POST /api/v1/auth/register`
- Purpose: create account and return signed auth token.
- `POST /api/v1/auth/login`
- Purpose: sign in with email/password (and MFA code if enabled).
- `GET /api/v1/auth/me`
- Purpose: resolve current user from bearer token.
- `POST /api/v1/auth/logout`
- Purpose: stateless logout acknowledgement.
- `POST /api/v1/auth/mfa/setup`
- Purpose: begin TOTP enrollment and return otpauth metadata.
- `POST /api/v1/auth/mfa/verify`
- Purpose: confirm MFA activation using TOTP code.
- `PATCH /api/v1/auth/admin/users/{user_id}/role`
- Purpose: admin-only role assignment.

### Payments

- `POST /api/v1/payments/stripe/setup-intent`
- Purpose: create payment intent and internal payment record.
- `POST /api/v1/payments/stripe/webhook`
- Purpose: Stripe webhook receiver that updates payment/access state.

### Assessment

- `POST /api/v1/assessment/start`
- Purpose: start/resume customer assessment after paid access is validated.
- `GET /api/v1/assessment/current`
- Purpose: fetch active in-progress assessment session.
- `PUT /api/v1/assessment/{assessment_id}/answers`
- Purpose: idempotent upsert of one answer per question.
- `POST /api/v1/assessment/{assessment_id}/submit`
- Purpose: finalize assessment and lock for report generation.

### Admin checklists

- Prefix: ` /api/v1/admin/checklists`
- Purpose: admin CRUD for checklists, sections, and questions, including publish lifecycle.

### Reports

- Prefix: `/api/v1/reports`
- Purpose: admin report lifecycle from draft generation to final publish.
- `POST /draft`
- Creates initial report findings from submitted assessment answers.
- `GET /assessment/{assessment_id}` / `GET /{report_id}`
- Fetch report status and metadata.
- `POST /{report_id}/review/start`
- Move report to under-review.
- `POST /{report_id}/review/request-changes`
- Mark report as changes-requested with reviewer note.
- `POST /{report_id}/summaries` and `GET /{report_id}/summaries`
- Create/update narrative summary blocks and list all summaries.
- `GET /{report_id}/findings`
- List generated findings used in report body.
- `POST /{report_id}/approve`
- Mark report as approved.
- `POST /{report_id}/publish`
- Publish final report with final PDF storage key.

## Report workflow sequence

1. Customer submits assessment.
2. Admin calls `POST /api/v1/reports/draft`.
3. System creates draft report and low-confidence findings.
4. Admin starts review and edits summary sections.
5. Admin approves report.
6. Admin publishes report by attaching final PDF storage key.

