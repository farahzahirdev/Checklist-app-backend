from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Health Check",
    description="Returns service liveness. Use this for uptime probes and basic API availability checks.",
)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
