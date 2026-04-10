from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
