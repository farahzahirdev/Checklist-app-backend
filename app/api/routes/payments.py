from fastapi import APIRouter, status

from app.schemas.common import MessageResponse

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/stripe/webhook", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def stripe_webhook_placeholder() -> MessageResponse:
    return MessageResponse(message="stripe_webhook_not_implemented")