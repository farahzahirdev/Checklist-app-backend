from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.access_window import AccessWindow
from app.models.checklist import Checklist, ChecklistStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.schemas.db import AccessWindowRead
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/access", tags=["access"])

@router.post(
    "/select-checklist",
    response_model=AccessWindowRead,
    summary="Select Checklist After Payment",
    description="Allows a user with a valid payment to select a checklist for 7-day access. Only one checklist can be selected per payment window.",
)
def select_checklist(
    checklist_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    # Check for active access window (from payment, not yet bound to a checklist)
    access_window = db.scalar(
        select(AccessWindow)
        .where(AccessWindow.user_id == current_user.id)
        .where(AccessWindow.activated_at <= now)
        .where(AccessWindow.expires_at > now)
        .where(AccessWindow.payment_id.isnot(None))
    )
    if not access_window:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no_active_payment_window")
    # Check if already bound to a checklist
    if getattr(access_window, "checklist_id", None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="checklist_already_selected")
    # Validate checklist
    checklist = db.get(Checklist, checklist_id)
    if not checklist or checklist.status != ChecklistStatus.published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invalid_checklist")
    # Bind checklist to access window
    access_window.checklist_id = checklist_id
    # Also update the payment record
    if access_window.payment_id:
        payment = db.get(Payment, access_window.payment_id)
        if payment:
            payment.checklist_id = checklist_id
            db.add(payment)
    db.add(access_window)
    db.commit()
    db.refresh(access_window)
    return access_window
