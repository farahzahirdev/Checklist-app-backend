from fastapi import APIRouter, status

from app.schemas.common import MessageResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def login_placeholder() -> MessageResponse:
    return MessageResponse(message="auth_login_not_implemented")