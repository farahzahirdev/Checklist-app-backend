"""API endpoints for customer payment records."""
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.customer_payments import (
    PaymentRecordListResponse,
    PaymentSummary,
    PaymentFilter,
    PaymentDashboardResponse,
    PaymentDetailResponse,
    PaymentAnalyticsResponse,
)

from app.services.customer_payments import (
    get_customer_payment_records,
    get_customer_payment_summary,
    get_customer_payment_dashboard,
    get_customer_payment_detail,
    get_customer_payment_analytics,
)

router = APIRouter(prefix="/customer/payments", tags=["customer-payments"])


@router.get(
    "/",
    response_model=PaymentRecordListResponse,
    summary="Get Payment Records",
    description="Get customer's payment records with filtering and pagination.",
)
def get_payment_records_endpoint(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by payment status"),
    checklist_id: Optional[UUID] = Query(None, description="Filter by checklist ID"),
    date_from: Optional[str] = Query(None, description="Filter by date from (ISO format)"),
    date_to: Optional[str] = Query(None, description="Filter by date to (ISO format)"),
    min_amount: Optional[int] = Query(None, description="Filter by minimum amount in cents"),
    max_amount: Optional[int] = Query(None, description="Filter by maximum amount in cents"),
    has_active_access: Optional[bool] = Query(None, description="Filter by active access status"),
    search: Optional[str] = Query(None, description="Search in checklist title or description"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    order_by: str = Query("created_at", description="Field to sort by"),
    order_direction: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentRecordListResponse:
    """Get customer's payment records."""
    
    # Parse date filters
    from datetime import datetime
    
    parsed_date_from = None
    parsed_date_to = None
    
    if date_from:
        try:
            parsed_date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format. Use ISO format.")
    
    if date_to:
        try:
            parsed_date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format. Use ISO format.")
    
    filters = PaymentFilter(
        status=status,
        checklist_id=checklist_id,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        has_active_access=has_active_access,
        search=search,
    )
    
    return get_customer_payment_records(
        db=db,
        user_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=limit,
        order_by=order_by,
        order_direction=order_direction
    )


@router.get(
    "/summary",
    response_model=PaymentSummary,
    summary="Get Payment Summary",
    description="Get customer's payment summary statistics.",
)
def get_payment_summary_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentSummary:
    """Get customer's payment summary."""
    
    return get_customer_payment_summary(db, current_user.id)


@router.get(
    "/dashboard",
    response_model=PaymentDashboardResponse,
    summary="Get Payment Dashboard",
    description="Get comprehensive payment dashboard for customer.",
)
def get_payment_dashboard_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentDashboardResponse:
    """Get customer's payment dashboard."""
    
    return get_customer_payment_dashboard(db, current_user.id)


@router.get(
    "/{payment_id}",
    response_model=PaymentDetailResponse,
    summary="Get Payment Details",
    description="Get detailed information about a specific payment.",
)
def get_payment_detail_endpoint(
    payment_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentDetailResponse:
    """Get detailed payment information."""
    
    payment_detail = get_customer_payment_detail(db, current_user.id, payment_id)
    if not payment_detail:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    return payment_detail


@router.get(
    "/analytics/overview",
    response_model=PaymentAnalyticsResponse,
    summary="Get Payment Analytics",
    description="Get comprehensive payment analytics for customer.",
)
def get_payment_analytics_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentAnalyticsResponse:
    """Get customer's payment analytics."""
    
    return get_customer_payment_analytics(db, current_user.id)


# Quick access endpoints for common customer payment scenarios

@router.get(
    "/recent",
    response_model=PaymentRecordListResponse,
    summary="Get Recent Payments",
    description="Get customer's most recent payments.",
)
def get_recent_payments_endpoint(
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="Number of recent payments to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentRecordListResponse:
    """Get customer's recent payments."""
    
    return get_customer_payment_records(
        db=db,
        user_id=current_user.id,
        skip=0,
        limit=limit,
        order_by="created_at",
        order_direction="desc"
    )


@router.get(
    "/successful",
    response_model=PaymentRecordListResponse,
    summary="Get Successful Payments",
    description="Get customer's successful payments only.",
)
def get_successful_payments_endpoint(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentRecordListResponse:
    """Get customer's successful payments."""
    
    filters = PaymentFilter(status="succeeded")
    
    return get_customer_payment_records(
        db=db,
        user_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=limit,
        order_by="created_at",
        order_direction="desc"
    )


@router.get(
    "/active-access",
    response_model=PaymentRecordListResponse,
    summary="Get Payments with Active Access",
    description="Get payments that currently provide active access to checklists.",
)
def get_active_access_payments_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentRecordListResponse:
    """Get payments with active access."""
    
    filters = PaymentFilter(has_active_access=True)
    
    return get_customer_payment_records(
        db=db,
        user_id=current_user.id,
        filters=filters,
        skip=0,
        limit=100,  # Higher limit for active access
        order_by="created_at",
        order_direction="desc"
    )


@router.get(
    "/by-checklist/{checklist_id}",
    response_model=PaymentRecordListResponse,
    summary="Get Payments by Checklist",
    description="Get all payments for a specific checklist.",
)
def get_payments_by_checklist_endpoint(
    checklist_id: UUID,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentRecordListResponse:
    """Get payments for a specific checklist."""
    
    filters = PaymentFilter(checklist_id=checklist_id)
    
    return get_customer_payment_records(
        db=db,
        user_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=limit,
        order_by="created_at",
        order_direction="desc"
    )


@router.get(
    "/stats/spending-by-month",
    summary="Get Spending by Month",
    description="Get customer's spending breakdown by month.",
)
def get_spending_by_month_endpoint(
    request: Request,
    months: int = Query(12, ge=1, le=24, description="Number of months to include"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """Get spending by month statistics."""
    
    analytics = get_customer_payment_analytics(db, current_user.id)
    
    # Return last N months
    return analytics.spending_by_month[-months:]


@router.get(
    "/stats/checklist-breakdown",
    summary="Get Checklist Spending Breakdown",
    description="Get customer's spending breakdown by checklist.",
)
def get_checklist_breakdown_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """Get checklist spending breakdown."""
    
    analytics = get_customer_payment_analytics(db, current_user.id)
    
    return analytics.spending_by_checklist


@router.get(
    "/stats/payment-frequency",
    summary="Get Payment Frequency",
    description="Get customer's payment frequency statistics.",
)
def get_payment_frequency_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get payment frequency statistics."""
    
    analytics = get_customer_payment_analytics(db, current_user.id)
    
    return {
        "payments_per_month": analytics.payment_frequency,
        "total_payments": analytics.payment_success_rate * 100,  # This is actually success rate, need to fix
        "average_amount": analytics.average_payment_amount,
        "total_spent": analytics.total_spent,
        "total_spent_formatted": analytics.total_spent_formatted,
    }


# Search and filtering endpoints

@router.get(
    "/search",
    response_model=PaymentRecordListResponse,
    summary="Search Payment Records",
    description="Search payment records by checklist title or description.",
)
def search_payment_records_endpoint(
    request: Request,
    q: str = Query(..., description="Search query"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentRecordListResponse:
    """Search payment records."""
    
    filters = PaymentFilter(search=q)
    
    return get_customer_payment_records(
        db=db,
        user_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=limit,
        order_by="created_at",
        order_direction="desc"
    )


@router.get(
    "/filter",
    response_model=PaymentRecordListResponse,
    summary="Filter Payment Records",
    description="Filter payment records by various criteria.",
)
def filter_payment_records_endpoint(
    request: Request,
    status: Optional[str] = Query(None),
    checklist_id: Optional[UUID] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    min_amount: Optional[int] = Query(None),
    max_amount: Optional[int] = Query(None),
    has_active_access: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    order_by: str = Query("created_at"),
    order_direction: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentRecordListResponse:
    """Filter payment records."""
    
    # Parse date filters
    from datetime import datetime
    
    parsed_date_from = None
    parsed_date_to = None
    
    if date_from:
        try:
            parsed_date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format. Use ISO format.")
    
    if date_to:
        try:
            parsed_date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format. Use ISO format.")
    
    filters = PaymentFilter(
        status=status,
        checklist_id=checklist_id,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        has_active_access=has_active_access,
    )
    
    return get_customer_payment_records(
        db=db,
        user_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=limit,
        order_by=order_by,
        order_direction=order_direction
    )


# Utility endpoints

@router.get(
    "/checklists/purchased",
    summary="Get Purchased Checklists",
    description="Get list of checklists the customer has purchased.",
)
def get_purchased_checklists_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """Get purchased checklists."""
    
    analytics = get_customer_payment_analytics(db, current_user.id)
    
    return [
        {
            "checklist_id": item.checklist_id,
            "checklist_title": item.checklist_title,
            "total_payments": item.total_payments,
            "total_amount": item.total_amount,
            "last_payment_date": item.last_payment_date.isoformat() if item.last_payment_date else None,
            "access_windows_granted": item.access_windows_granted,
        }
        for item in analytics.spending_by_checklist
    ]


@router.get(
    "/access/active",
    summary="Get Active Access",
    description="Get currently active access windows.",
)
def get_active_access_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """Get currently active access windows."""
    
    dashboard = get_customer_payment_dashboard(db, current_user.id)
    
    return [
        {
            "access_window_id": item.id,
            "payment_id": item.payment_id,
            "checklist_id": item.checklist_id,
            "checklist_title": item.checklist_title,
            "start_date": item.start_date.isoformat(),
            "end_date": item.end_date.isoformat(),
            "days_remaining": item.days_remaining,
            "days_total": item.days_total,
            "access_percentage": item.access_percentage,
        }
        for item in dashboard.active_access_windows
    ]


@router.get(
    "/access/upcoming-expirations",
    summary="Get Upcoming Expirations",
    description="Get access windows expiring in the next 7 days.",
)
def get_upcoming_expirations_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """Get upcoming access window expirations."""
    
    dashboard = get_customer_payment_dashboard(db, current_user.id)
    
    return [
        {
            "access_window_id": item.id,
            "payment_id": item.payment_id,
            "checklist_id": item.checklist_id,
            "checklist_title": item.checklist_title,
            "end_date": item.end_date.isoformat(),
            "days_remaining": item.days_remaining,
            "days_total": item.days_total,
        }
        for item in dashboard.upcoming_expirations
    ]
