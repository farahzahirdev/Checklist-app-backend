from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
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
from app.services.company_context import resolve_company_id, user_has_company_access
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate

router = APIRouter(prefix="/access", tags=["access"])

@router.post(
    "/select-checklist",
    response_model=AccessWindowRead,
    summary="Select Checklist After Payment",
    description="Allows a user with a valid payment to select a checklist for 7-day access. Only one checklist can be selected per payment window.",
)
def select_checklist(
    checklist_id: UUID,
    request: Request,
    company_id: UUID | None = Query(None, description="Optional company/tenant ID for the active purchase flow"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lang_code = get_language_code(request, db)
    now = datetime.now(timezone.utc)
    resolved_company_id = resolve_company_id(current_user, company_id)
    if not user_has_company_access(db, user=current_user, company_id=resolved_company_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("forbidden", lang_code))

    # Check for active access window (from payment, not yet bound to a checklist)
    access_window_query = select(AccessWindow).where(
        AccessWindow.user_id == current_user.id,
        AccessWindow.activated_at <= now,
        AccessWindow.expires_at > now,
        AccessWindow.payment_id.isnot(None),
    )
    if resolved_company_id is not None:
        access_window_query = access_window_query.where(AccessWindow.company_id == resolved_company_id)
    access_window = db.scalar(access_window_query)
    if not access_window:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("no_active_payment_window", lang_code))
    # Check if already bound to a checklist
    if getattr(access_window, "checklist_id", None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("checklist_already_selected", lang_code))
    # Validate checklist
    checklist = db.get(Checklist, checklist_id)
    if not checklist or checklist.status != ChecklistStatus.published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("invalid_checklist", lang_code))
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
