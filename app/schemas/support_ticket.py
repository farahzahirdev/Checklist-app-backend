from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.support_ticket import SupportTicketStatus


class SupportTicketCreateRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    message: str = Field(min_length=1, max_length=5000)


class SupportTicketReplyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class SupportTicketStatusUpdateRequest(BaseModel):
    status: SupportTicketStatus


class SupportTicketMessageResponse(BaseModel):
    id: UUID
    ticket_id: UUID
    sender_user_id: UUID
    sender_role: str
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class SupportTicketResponse(BaseModel):
    id: UUID
    customer_id: UUID
    customer_email: str
    subject: str
    status: SupportTicketStatus
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime
    messages: list[SupportTicketMessageResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class SupportTicketListResponse(BaseModel):
    total: int
    tickets: list[SupportTicketResponse]
    skip: int
    limit: int
