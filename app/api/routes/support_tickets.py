from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.support_ticket import SupportTicketStatus
from app.models.user import User, UserRole
from app.schemas.support_ticket import (
    SupportTicketCreateRequest,
    SupportTicketListResponse,
    SupportTicketReplyRequest,
    SupportTicketResponse,
    SupportTicketStatusUpdateRequest,
)
from app.services.support_tickets import (
    create_ticket,
    get_ticket_for_admin,
    get_ticket_for_customer,
    list_all_tickets,
    list_customer_tickets,
    reply_to_ticket,
    serialize_ticket,
    set_ticket_status,
)
from app.utils.i18n import get_language_code


customer_router = APIRouter(prefix="/customer/support", tags=["customer-support"])
admin_router = APIRouter(prefix="/admin/support", tags=["admin-support"])


@customer_router.get("/tickets", response_model=SupportTicketListResponse)
def list_my_tickets(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    if current_user.role != UserRole.customer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can access support tickets")
    return list_customer_tickets(db, customer=current_user, skip=skip, limit=limit)


@customer_router.post("/tickets", response_model=SupportTicketResponse)
def create_my_ticket(
    request: Request,
    payload: SupportTicketCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    if current_user.role != UserRole.customer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can create support tickets")
    return create_ticket(db, customer=current_user, subject=payload.subject, message=payload.message)


@customer_router.get("/tickets/{ticket_id}", response_model=SupportTicketResponse)
def get_my_ticket(
    ticket_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    if current_user.role != UserRole.customer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can access support tickets")
    ticket = get_ticket_for_customer(db, ticket_id=ticket_id, customer=current_user)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="support_ticket_not_found")
    return serialize_ticket(db, ticket, include_messages=True)


@customer_router.post("/tickets/{ticket_id}/reply", response_model=SupportTicketResponse)
def reply_to_my_ticket(
    ticket_id: UUID,
    request: Request,
    payload: SupportTicketReplyRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    if current_user.role != UserRole.customer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can reply to support tickets")
    ticket = get_ticket_for_customer(db, ticket_id=ticket_id, customer=current_user)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="support_ticket_not_found")
    try:
        return reply_to_ticket(db, ticket=ticket, sender=current_user, message=payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@admin_router.get("/tickets", response_model=SupportTicketListResponse)
def list_tickets(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: SupportTicketStatus | None = Query(None, alias="status"),
    search: str | None = Query(None),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access support tickets")
    return list_all_tickets(db, skip=skip, limit=limit, status=status_filter.value if status_filter else None, search=search)


@admin_router.get("/tickets/{ticket_id}", response_model=SupportTicketResponse)
def get_ticket(
    ticket_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access support tickets")
    ticket = get_ticket_for_admin(db, ticket_id=ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="support_ticket_not_found")
    return serialize_ticket(db, ticket, include_messages=True)


@admin_router.post("/tickets/{ticket_id}/reply", response_model=SupportTicketResponse)
def reply_to_ticket_as_admin(
    ticket_id: UUID,
    request: Request,
    payload: SupportTicketReplyRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can reply to support tickets")
    ticket = get_ticket_for_admin(db, ticket_id=ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="support_ticket_not_found")
    try:
        return reply_to_ticket(db, ticket=ticket, sender=current_user, message=payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@admin_router.patch("/tickets/{ticket_id}/status", response_model=SupportTicketResponse)
def update_ticket_status(
    ticket_id: UUID,
    request: Request,
    payload: SupportTicketStatusUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can update support tickets")
    ticket = get_ticket_for_admin(db, ticket_id=ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="support_ticket_not_found")
    return set_ticket_status(db, ticket=ticket, status=payload.status)


router = APIRouter()
router.include_router(customer_router)
router.include_router(admin_router)
