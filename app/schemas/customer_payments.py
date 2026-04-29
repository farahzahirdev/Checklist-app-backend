"""Schemas for customer payment records API."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentRecord(BaseModel):
    """Schema for individual payment record."""
    id: UUID
    user_id: UUID
    checklist_id: Optional[UUID]
    checklist_title: Optional[str] = None
    checklist_description: Optional[str] = None
    checklist_version: Optional[str] = None
    stripe_payment_intent_id: str
    amount_cents: int
    amount_formatted: str  # Formatted currency string
    currency: str
    status: str
    paid_at: Optional[datetime]
    created_at: datetime
    access_window_start: Optional[datetime] = None
    access_window_end: Optional[datetime] = None
    is_access_active: bool = False
    days_of_access: Optional[int] = None
    
    class Config:
        from_attributes = True


class PaymentSummary(BaseModel):
    """Schema for payment summary statistics."""
    total_payments: int
    total_amount_cents: int
    total_amount_formatted: str
    successful_payments: int
    failed_payments: int
    pending_payments: int
    average_payment_amount: float
    most_recent_payment: Optional[PaymentRecord]
    total_checklists_purchased: int
    active_access_windows: int
    
    class Config:
        from_attributes = True


class PaymentRecordListResponse(BaseModel):
    """Schema for payment records list response."""
    payments: List[PaymentRecord]
    total: int
    page: int
    size: int
    pages: int
    summary: Optional[PaymentSummary] = None
    
    class Config:
        from_attributes = True


class PaymentFilter(BaseModel):
    """Schema for filtering payment records."""
    status: Optional[str] = Field(None, description="Filter by payment status")
    checklist_id: Optional[UUID] = Field(None, description="Filter by checklist ID")
    date_from: Optional[datetime] = Field(None, description="Filter by date from (inclusive)")
    date_to: Optional[datetime] = Field(None, description="Filter by date to (inclusive)")
    min_amount: Optional[int] = Field(None, description="Filter by minimum amount in cents")
    max_amount: Optional[int] = Field(None, description="Filter by maximum amount in cents")
    has_active_access: Optional[bool] = Field(None, description="Filter by active access status")
    search: Optional[str] = Field(None, description="Search in checklist title or description")


class AccessWindowInfo(BaseModel):
    """Schema for access window information."""
    id: UUID
    payment_id: UUID
    checklist_id: Optional[UUID]
    checklist_title: Optional[str]
    start_date: datetime
    end_date: datetime
    is_active: bool
    days_remaining: Optional[int] = None
    days_total: int
    access_percentage: float  # 0-100 representing progress through access period
    
    class Config:
        from_attributes = True


class PaymentTrend(BaseModel):
    """Schema for payment trend data."""
    period: str  # e.g., "2026-04", "2026-04-27"
    payment_count: int
    total_amount: int
    average_amount: float
    
    class Config:
        from_attributes = True


class ChecklistPaymentStats(BaseModel):
    """Schema for checklist payment statistics."""
    checklist_id: UUID
    checklist_title: str
    checklist_description: Optional[str]
    total_payments: int
    total_amount: int
    average_amount: float
    last_payment_date: Optional[datetime]
    access_windows_granted: int
    is_most_purchased: bool = False
    
    class Config:
        from_attributes = True


class PaymentDashboardResponse(BaseModel):
    """Schema for customer payment dashboard."""
    summary: PaymentSummary
    recent_payments: List[PaymentRecord]
    active_access_windows: List[AccessWindowInfo]
    upcoming_expirations: List[AccessWindowInfo]
    payment_trends: List[PaymentTrend]
    checklist_breakdown: List[ChecklistPaymentStats]
    
    class Config:
        from_attributes = True


class ChecklistInfo(BaseModel):
    """Schema for checklist information."""
    id: UUID
    title: str
    description: Optional[str]
    version: str
    price_cents: int
    price_formatted: str
    category: Optional[str]
    difficulty_level: Optional[str]
    estimated_duration_hours: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PaymentHistoryItem(BaseModel):
    """Schema for payment history item."""
    id: UUID
    payment_id: UUID
    action: str  # created, updated, succeeded, failed, refunded
    previous_status: Optional[str]
    new_status: Optional[str]
    description: str
    metadata: Optional[dict]
    created_at: datetime
    
    class Config:
        from_attributes = True


class RefundInfo(BaseModel):
    """Schema for refund information."""
    id: UUID
    payment_id: UUID
    amount_cents: int
    amount_formatted: str
    reason: Optional[str]
    status: str  # pending, processed, rejected
    processed_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class PaymentTrend(BaseModel):
    """Schema for payment trend data."""
    period: str  # e.g., "2026-04", "2026-04-27"
    payment_count: int
    total_amount: int
    average_amount: float
    
    class Config:
        from_attributes = True


class ChecklistPaymentStats(BaseModel):
    """Schema for checklist payment statistics."""
    checklist_id: UUID
    checklist_title: str
    checklist_description: Optional[str]
    total_payments: int
    total_amount: int
    average_amount: float
    last_payment_date: Optional[datetime]
    access_windows_granted: int
    is_most_purchased: bool = False
    
    class Config:
        from_attributes = True


class PaymentDetailResponse(BaseModel):
    """Schema for detailed payment information."""
    payment: PaymentRecord
    access_windows: List[AccessWindowInfo]
    checklist_info: Optional[ChecklistInfo] = None
    payment_history: List[PaymentHistoryItem]
    refund_info: Optional[RefundInfo] = None
    
    class Config:
        from_attributes = True


class ChecklistInfo(BaseModel):
    """Schema for checklist information."""
    id: UUID
    title: str
    description: Optional[str]
    version: str
    price_cents: int
    price_formatted: str
    category: Optional[str]
    difficulty_level: Optional[str]
    estimated_duration_hours: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PaymentHistoryItem(BaseModel):
    """Schema for payment history item."""
    id: UUID
    payment_id: UUID
    action: str  # created, updated, succeeded, failed, refunded
    previous_status: Optional[str]
    new_status: Optional[str]
    description: str
    metadata: Optional[dict]
    created_at: datetime
    
    class Config:
        from_attributes = True


class RefundInfo(BaseModel):
    """Schema for refund information."""
    id: UUID
    payment_id: UUID
    amount_cents: int
    amount_formatted: str
    reason: Optional[str]
    status: str  # pending, processed, rejected
    processed_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class MonthlySpending(BaseModel):
    """Schema for monthly spending data."""
    month: str  # e.g., "2026-04"
    amount_cents: int
    amount_formatted: str
    payment_count: int
    average_amount: float
    
    class Config:
        from_attributes = True


class PaymentAnalyticsResponse(BaseModel):
    """Schema for payment analytics."""
    total_spent: int
    total_spent_formatted: str
    payment_frequency: float  # payments per month
    average_payment_amount: float
    most_expensive_payment: Optional[PaymentRecord]
    most_frequent_checklist: Optional[ChecklistPaymentStats]
    spending_by_month: List[MonthlySpending]
    spending_by_checklist: List[ChecklistPaymentStats]
    payment_success_rate: float
    total_access_days: int
    average_access_duration: float
    
    class Config:
        from_attributes = True


class MonthlySpending(BaseModel):
    """Schema for monthly spending data."""
    month: str  # e.g., "2026-04"
    amount_cents: int
    amount_formatted: str
    payment_count: int
    average_amount: float
    
    class Config:
        from_attributes = True


class PaymentRequest(BaseModel):
    """Schema for payment request (for future use)."""
    checklist_id: UUID
    payment_method_id: Optional[str] = None
    amount_cents: Optional[int] = None  # If not provided, use checklist price
    
    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):
    """Schema for payment response."""
    payment: PaymentRecord
    client_secret: Optional[str] = None  # For Stripe payment intent
    payment_url: Optional[str] = None   # For payment completion
    success: bool
    message: str
    
    class Config:
        from_attributes = True


class BulkPaymentRequest(BaseModel):
    """Schema for bulk payment request (multiple checklists)."""
    checklist_ids: List[UUID]
    payment_method_id: Optional[str] = None
    
    class Config:
        from_attributes = True


class BulkPaymentResponse(BaseModel):
    """Schema for bulk payment response."""
    payments: List[PaymentRecord]
    total_amount_cents: int
    total_amount_formatted: str
    success: bool
    message: str
    failed_checklists: List[UUID] = []
    
    class Config:
        from_attributes = True
