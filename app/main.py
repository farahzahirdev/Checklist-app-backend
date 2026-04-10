from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.schemas.access import AccessWindowResponse
from app.schemas.auth import LoginRequest, RoleAssignment
from app.schemas.common import MessageResponse
from app.schemas.db import AccessWindowCreate, AccessWindowRead, PaymentCreate, PaymentRead, UserCreate, UserRead
from app.schemas.health import HealthResponse
from app.schemas.payment import PaymentState

settings = get_settings()
configure_logging(settings.app_name)

app = FastAPI(title=settings.app_name)
app.include_router(api_router, prefix=settings.api_v1_prefix)


def custom_openapi() -> dict:
	if app.openapi_schema:
		return app.openapi_schema

	openapi_schema = get_openapi(
		title=app.title,
		version="0.1.0",
		description="Checklist App API",
		routes=app.routes,
	)

	components = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
	models = [
		MessageResponse,
		HealthResponse,
		LoginRequest,
		RoleAssignment,
		PaymentState,
		AccessWindowResponse,
		UserCreate,
		UserRead,
		PaymentCreate,
		PaymentRead,
		AccessWindowCreate,
		AccessWindowRead,
	]

	for model in models:
		schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
		for def_name, def_schema in schema.pop("$defs", {}).items():
			components.setdefault(def_name, def_schema)
		components.setdefault(model.__name__, schema)

	app.openapi_schema = openapi_schema
	return app.openapi_schema


app.openapi = custom_openapi
