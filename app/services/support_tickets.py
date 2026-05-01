from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.support_ticket import SupportTicket, SupportTicketMessage, SupportTicketStatus
from app.models.user import User, UserRole


def _serialize_message(message: SupportTicketMessage) -> dict:
    return {
        "id": message.id,
        "ticket_id": message.ticket_id,
        "sender_user_id": message.sender_user_id,
        "sender_role": message.sender_role,
        "body": message.body,
        "created_at": message.created_at,
    }


def serialize_ticket(db: Session, ticket: SupportTicket, include_messages: bool = True) -> dict:
    customer_email = db.scalar(select(User.email).where(User.id == ticket.customer_id)) or ""
    payload = {
        "id": ticket.id,
        "customer_id": ticket.customer_id,
        "customer_email": customer_email,
        "subject": ticket.subject,
        "status": SupportTicketStatus(ticket.status),
        "last_message_at": ticket.last_message_at,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "messages": [],
    }
    if include_messages:
        payload["messages"] = [_serialize_message(message) for message in ticket.messages]
    return payload


def create_ticket(db: Session, *, customer: User, subject: str, message: str) -> dict:
    ticket = SupportTicket(
        customer_id=customer.id,
        subject=subject.strip(),
        status=SupportTicketStatus.open.value,
    )
    db.add(ticket)
    db.flush()

    ticket_message = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_user_id=customer.id,
        sender_role=str(customer.role),
        body=message.strip(),
    )
    db.add(ticket_message)
    ticket.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return serialize_ticket(db, ticket, include_messages=True)


def list_customer_tickets(db: Session, *, customer: User, skip: int = 0, limit: int = 20) -> dict:
    query = (
        db.query(SupportTicket)
        .filter(SupportTicket.customer_id == customer.id)
        .order_by(SupportTicket.updated_at.desc())
    )
    total = query.count()
    tickets = query.offset(skip).limit(limit).all()
    return {"total": total, "tickets": [serialize_ticket(db, ticket, include_messages=True) for ticket in tickets], "skip": skip, "limit": limit}


def list_all_tickets(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    search: str | None = None,
) -> dict:
    query = db.query(SupportTicket).join(User, User.id == SupportTicket.customer_id)
    if status:
        query = query.filter(SupportTicket.status == status)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(SupportTicket.subject.ilike(term), User.email.ilike(term)))
    query = query.order_by(SupportTicket.updated_at.desc())
    total = query.count()
    tickets = query.offset(skip).limit(limit).all()
    return {"total": total, "tickets": [serialize_ticket(db, ticket, include_messages=False) for ticket in tickets], "skip": skip, "limit": limit}


def get_ticket_for_customer(db: Session, *, ticket_id, customer: User) -> SupportTicket | None:
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.customer_id != customer.id:
        return None
    return ticket


def get_ticket_for_admin(db: Session, *, ticket_id) -> SupportTicket | None:
    return db.get(SupportTicket, ticket_id)


def reply_to_ticket(db: Session, *, ticket: SupportTicket, sender: User, message: str) -> dict:
    if ticket.status == SupportTicketStatus.closed.value:
        raise ValueError("support_ticket_closed")

    reply = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_user_id=sender.id,
        sender_role=str(sender.role),
        body=message.strip(),
    )
    db.add(reply)
    ticket.last_message_at = datetime.now(timezone.utc)
    ticket.status = SupportTicketStatus.waiting_customer.value if sender.role == UserRole.admin.value else SupportTicketStatus.open.value
    db.commit()
    db.refresh(ticket)
    return serialize_ticket(db, ticket, include_messages=True)


def set_ticket_status(db: Session, *, ticket: SupportTicket, status: SupportTicketStatus) -> dict:
    ticket.status = status.value
    db.commit()
    db.refresh(ticket)
    return serialize_ticket(db, ticket, include_messages=True)
