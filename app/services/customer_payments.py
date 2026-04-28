"""Service layer for customer payment records."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import func, select, and_, or_, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.models.payment import Payment, PaymentStatus
from app.models.checklist import Checklist
from app.models.checklist import ChecklistTranslation
from app.models.access_window import AccessWindow
from app.models.user import User
from app.schemas.customer_payments import (
    PaymentRecord,
    PaymentRecordListResponse,
    PaymentSummary,
    PaymentFilter,
    PaymentDashboardResponse,
    AccessWindowInfo,
    PaymentTrend,
    ChecklistPaymentStats,
    PaymentDetailResponse,
    ChecklistInfo,
    PaymentHistoryItem,
    PaymentAnalyticsResponse,
    MonthlySpending,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _format_currency(amount_cents: int, currency: str = "USD") -> str:
    """Format amount in cents to currency string."""
    amount_dollars = amount_cents / 100
    if currency == "USD":
        return f"${amount_dollars:.2f}"
    return f"{amount_dollars:.2f} {currency}"


def get_customer_payment_records(
    db: Session,
    user_id: UUID,
    filters: Optional[PaymentFilter] = None,
    skip: int = 0,
    limit: int = 50,
    order_by: str = "created_at",
    order_direction: str = "desc"
) -> PaymentRecordListResponse:
    """Get payment records for a customer with filtering and pagination."""
    
    # Base query with joins to get checklist info
    query = (
        db.query(Payment, Checklist)
        .outerjoin(Checklist, Payment.checklist_id == Checklist.id)
        .filter(Payment.user_id == user_id)
    )
    
    # Apply filters
    if filters:
        if filters.status:
            query = query.filter(Payment.status == filters.status)
        
        if filters.checklist_id:
            query = query.filter(Payment.checklist_id == filters.checklist_id)
        
        if filters.date_from:
            query = query.filter(Payment.created_at >= filters.date_from)
        
        if filters.date_to:
            query = query.filter(Payment.created_at <= filters.date_to)
        
        if filters.min_amount:
            query = query.filter(Payment.amount_cents >= filters.min_amount)
        
        if filters.max_amount:
            query = query.filter(Payment.amount_cents <= filters.max_amount)
        
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Checklist.title.ilike(search_term),
                    Checklist.description.ilike(search_term),
                )
            )
    
    # Count total
    total = query.count()
    
    # Apply ordering
    order_column = getattr(Payment, order_by, Payment.created_at)
    if order_direction.lower() == "desc":
        query = query.order_by(desc(order_column))
    else:
        query = query.order_by(asc(order_column))
    
    # Apply pagination
    results = query.offset(skip).limit(limit).all()
    
    # Build payment records
    payment_records = []
    for payment, checklist in results:
        # Get access windows for this payment
        access_windows = db.query(AccessWindow).filter(
            AccessWindow.payment_id == payment.id
        ).all()
        
        # Determine access status
        active_access = any(
            window.activated_at <= _now_utc() <= window.expires_at 
            for window in access_windows
        )
        
        # Calculate days of access
        total_days = sum(
            (window.expires_at - window.activated_at).days + 1
            for window in access_windows
        )
        
        payment_record = PaymentRecord(
            id=payment.id,
            user_id=payment.user_id,
            checklist_id=payment.checklist_id,
            checklist_title=checklist.title if checklist else None,
            checklist_description=checklist.description if checklist else None,
            checklist_version=checklist.version if checklist else None,
            stripe_payment_intent_id=payment.stripe_payment_intent_id,
            amount_cents=payment.amount_cents,
            amount_formatted=_format_currency(payment.amount_cents, payment.currency),
            currency=payment.currency,
            status=payment.status,
            paid_at=payment.paid_at,
            created_at=payment.created_at,
            access_window_start=min((w.activated_at for w in access_windows), default=None),
            access_window_end=max((w.expires_at for w in access_windows), default=None),
            is_access_active=active_access,
            days_of_access=total_days if total_days > 0 else None,
        )
        
        payment_records.append(payment_record)
    
    # Calculate pagination info
    pages = (total + limit - 1) // limit if limit > 0 else 0
    page = (skip // limit) + 1 if limit > 0 else 1
    
    return PaymentRecordListResponse(
        payments=payment_records,
        total=total,
        page=page,
        size=limit,
        pages=pages,
    )


def get_customer_payment_summary(db: Session, user_id: UUID) -> PaymentSummary:
    """Get payment summary for a customer."""
    
    # Get all payments for user
    payments = db.query(Payment).filter(Payment.user_id == user_id).all()
    
    if not payments:
        return PaymentSummary(
            total_payments=0,
            total_amount_cents=0,
            total_amount_formatted="$0.00",
            successful_payments=0,
            failed_payments=0,
            pending_payments=0,
            average_payment_amount=0.0,
            most_recent_payment=None,
            total_checklists_purchased=0,
            active_access_windows=0,
        )
    
    # Calculate summary statistics
    total_payments = len(payments)
    total_amount_cents = sum(p.amount_cents for p in payments)
    successful_payments = len([p for p in payments if p.status == PaymentStatus.succeeded])
    failed_payments = len([p for p in payments if p.status == PaymentStatus.failed])
    pending_payments = len([p for p in payments if p.status == PaymentStatus.pending])
    average_payment_amount = total_amount_cents / total_payments if total_payments > 0 else 0
    
    # Most recent payment
    most_recent_payment = max(payments, key=lambda p: p.created_at)
    
    # Total unique checklists purchased
    unique_checklists = len(set(p.checklist_id for p in payments if p.checklist_id))
    
    # Active access windows
    now = _now_utc()
    active_access_windows = (
        db.query(AccessWindow)
        .join(Payment, AccessWindow.payment_id == Payment.id)
        .filter(
            and_(
                Payment.user_id == user_id,
                AccessWindow.activated_at <= now,
                AccessWindow.expires_at >= now
            )
        )
        .count()
    )
    
    return PaymentSummary(
        total_payments=total_payments,
        total_amount_cents=total_amount_cents,
        total_amount_formatted=_format_currency(total_amount_cents),
        successful_payments=successful_payments,
        failed_payments=failed_payments,
        pending_payments=pending_payments,
        average_payment_amount=average_payment_amount,
        most_recent_payment=None,  # Would need to build full PaymentRecord
        total_checklists_purchased=unique_checklists,
        active_access_windows=active_access_windows,
    )


def get_customer_payment_dashboard(db: Session, user_id: UUID) -> PaymentDashboardResponse:
    """Get comprehensive payment dashboard for a customer."""
    
    # Get summary
    summary = get_customer_payment_summary(db, user_id)
    
    # Get recent payments (last 5)
    recent_payments_result = get_customer_payment_records(
        db, user_id, skip=0, limit=5, order_by="created_at", order_direction="desc"
    )
    
    # Get active access windows
    now = _now_utc()
    active_access_windows_query = (
        db.query(AccessWindow, Payment, Checklist)
        .join(Payment, AccessWindow.payment_id == Payment.id)
        .outerjoin(Checklist, Payment.checklist_id == Checklist.id)
        .filter(
            and_(
                Payment.user_id == user_id,
                AccessWindow.activated_at <= now,
                AccessWindow.expires_at >= now
            )
        )
        .order_by(AccessWindow.expires_at)
        .all()
    )
    
    active_access_windows = []
    for access_window, payment, checklist in active_access_windows_query:
        days_remaining = (access_window.expires_at - now).days + 1
        days_total = (access_window.expires_at - access_window.activated_at).days + 1
        access_percentage = ((now - access_window.activated_at).days + 1) / days_total * 100
        
        active_access_windows.append(AccessWindowInfo(
            id=access_window.id,
            payment_id=payment.id,
            checklist_id=payment.checklist_id,
            checklist_title=checklist.title if checklist else None,
            start_date=access_window.activated_at,
            end_date=access_window.expires_at,
            is_active=True,
            days_remaining=days_remaining,
            days_total=days_total,
            access_percentage=min(access_percentage, 100),
        ))
    
    # Get upcoming expirations (next 7 days)
    upcoming_end_date = now + timedelta(days=7)
    upcoming_expirations_query = (
        db.query(AccessWindow, Payment, Checklist)
        .join(Payment, AccessWindow.payment_id == Payment.id)
        .outerjoin(Checklist, Payment.checklist_id == Checklist.id)
        .filter(
            and_(
                Payment.user_id == user_id,
                AccessWindow.expires_at > now,
                AccessWindow.expires_at <= upcoming_end_date,
                AccessWindow.expires_at > now  # Exclude currently active
            )
        )
        .order_by(AccessWindow.expires_at)
        .all()
    )
    
    upcoming_expirations = []
    for access_window, payment, checklist in upcoming_expirations_query:
        days_total = (access_window.expires_at - access_window.activated_at).days + 1
        
        days_remaining = (access_window.expires_at - now).days + 1
        upcoming_expirations.append(AccessWindowInfo(
            id=access_window.id,
            payment_id=payment.id,
            checklist_id=payment.checklist_id,
            checklist_title=checklist.title if checklist else None,
            start_date=access_window.activated_at,
            end_date=access_window.expires_at,
            is_active=False,
            days_remaining=days_remaining,
            days_total=days_total,
            access_percentage=100,  # Will be 100% when expired
        ))
    
    # Get payment trends (last 6 months)
    six_months_ago = now - timedelta(days=180)
    payment_trends_query = (
        db.query(
            func.date_trunc('month', Payment.created_at).label('month'),
            func.count(Payment.id).label('payment_count'),
            func.sum(Payment.amount_cents).label('total_amount'),
            func.avg(Payment.amount_cents).label('average_amount'),
        )
        .filter(
            and_(
                Payment.user_id == user_id,
                Payment.created_at >= six_months_ago,
                Payment.status == PaymentStatus.succeeded
            )
        )
        .group_by(func.date_trunc('month', Payment.created_at))
        .order_by('month')
        .all()
    )
    
    payment_trends = []
    for month, payment_count, total_amount, average_amount in payment_trends_query:
        payment_trends.append(PaymentTrend(
            period=month.strftime("%Y-%m"),
            payment_count=payment_count,
            total_amount=total_amount or 0,
            average_amount=float(average_amount or 0),
        ))
    
    # Get checklist breakdown
    checklist_breakdown_query = (
        db.query(
            Checklist.id,
            Checklist.title,
            Checklist.description,
            func.count(Payment.id).label('total_payments'),
            func.sum(Payment.amount_cents).label('total_amount'),
            func.avg(Payment.amount_cents).label('average_amount'),
            func.max(Payment.created_at).label('last_payment_date'),
            func.count(func.distinct(AccessWindow.id)).label('access_windows_granted'),
        )
        .outerjoin(Payment, Checklist.id == Payment.checklist_id)
        .outerjoin(AccessWindow, Payment.id == AccessWindow.payment_id)
        .filter(Payment.user_id == user_id)
        .group_by(Checklist.id, Checklist.title, Checklist.description)
        .order_by(desc('total_payments'))
        .all()
    )
    
    checklist_breakdown = []
    max_payments = 0
    if checklist_breakdown_query:
        max_payments = max(cb.total_payments for cb in checklist_breakdown_query)
    
    for cb in checklist_breakdown_query:
        checklist_breakdown.append(ChecklistPaymentStats(
            checklist_id=cb.id,
            checklist_title=cb.title,
            checklist_description=cb.description,
            total_payments=cb.total_payments,
            total_amount=cb.total_amount or 0,
            average_amount=float(cb.average_amount or 0),
            last_payment_date=cb.last_payment_date,
            access_windows_granted=cb.access_windows_granted or 0,
            is_most_purchased=cb.total_payments == max_payments,
        ))
    
    return PaymentDashboardResponse(
        summary=summary,
        recent_payments=recent_payments_result.payments,
        active_access_windows=active_access_windows,
        upcoming_expirations=upcoming_expirations,
        payment_trends=payment_trends,
        checklist_breakdown=checklist_breakdown,
    )


def get_customer_payment_detail(
    db: Session,
    user_id: UUID,
    payment_id: UUID
) -> Optional[PaymentDetailResponse]:
    """Get detailed payment information for a customer."""
    
    # Get payment with checklist info
    payment_query = (
        db.query(Payment, Checklist)
        .outerjoin(Checklist, Payment.checklist_id == Checklist.id)
        .filter(
            and_(
                Payment.id == payment_id,
                Payment.user_id == user_id
            )
        )
        .first()
    )
    
    if not payment_query:
        return None
    
    payment, checklist = payment_query
    
    # Get access windows
    access_windows_query = (
        db.query(AccessWindow)
        .filter(AccessWindow.payment_id == payment_id)
        .order_by(AccessWindow.activated_at)
        .all()
    )
    
    access_windows = []
    for access_window in access_windows_query:
        days_total = (access_window.expires_at - access_window.activated_at).days + 1
        now = _now_utc()
        days_remaining = max(0, (access_window.expires_at - now).days + 1)
        access_percentage = 0
        
        if access_window.activated_at <= now <= access_window.expires_at:
            elapsed = (now - access_window.activated_at).days + 1
            access_percentage = (elapsed / days_total) * 100
        elif now > access_window.expires_at:
            access_percentage = 100
        
        access_windows.append(AccessWindowInfo(
            id=access_window.id,
            payment_id=payment.id,
            checklist_id=payment.checklist_id,
            checklist_title=checklist.title if checklist else None,
            start_date=access_window.activated_at,
            end_date=access_window.expires_at,
            is_active=access_window.activated_at <= now <= access_window.expires_at,
            days_remaining=days_remaining if access_window.expires_at > now else 0,
            days_total=days_total,
            access_percentage=min(access_percentage, 100),
        ))
    
    # Build checklist info
    checklist_info = None
    if checklist:
        checklist_info = ChecklistInfo(
            id=checklist.id,
            title=checklist.title,
            description=checklist.description,
            version=checklist.version,
            price_cents=checklist.price_cents,
            price_formatted=_format_currency(checklist.price_cents),
            category=checklist.category,
            difficulty_level=checklist.difficulty_level,
            estimated_duration_hours=checklist.estimated_duration_hours,
            is_active=checklist.is_active,
            created_at=checklist.created_at,
            updated_at=checklist.updated_at,
        )
    
    # Build payment record
    active_access = any(
        window.activated_at <= _now_utc() <= window.expires_at 
        for window in access_windows_query
    )
    
    payment_record = PaymentRecord(
        id=payment.id,
        user_id=payment.user_id,
        checklist_id=payment.checklist_id,
        checklist_title=checklist.title if checklist else None,
        checklist_description=checklist.description if checklist else None,
        checklist_version=checklist.version if checklist else None,
        stripe_payment_intent_id=payment.stripe_payment_intent_id,
        amount_cents=payment.amount_cents,
        amount_formatted=_format_currency(payment.amount_cents, payment.currency),
        currency=payment.currency,
        status=payment.status,
        paid_at=payment.paid_at,
        created_at=payment.created_at,
        access_window_start=min((w.activated_at for w in access_windows_query), default=None),
        access_window_end=max((w.expires_at for w in access_windows_query), default=None),
        is_access_active=active_access,
        days_of_access=sum(
            (w.expires_at - w.activated_at).days + 1 for w in access_windows_query
        ) if access_windows_query else None,
    )
    
    return PaymentDetailResponse(
        payment=payment_record,
        access_windows=access_windows,
        checklist_info=checklist_info,
        payment_history=[],  # TODO: Implement payment history tracking
        refund_info=None,     # TODO: Implement refund tracking
    )


def get_customer_payment_analytics(db: Session, user_id: UUID) -> PaymentAnalyticsResponse:
    """Get payment analytics for a customer."""
    
    # Get all successful payments
    successful_payments = (
        db.query(Payment)
        .filter(
            and_(
                Payment.user_id == user_id,
                Payment.status == PaymentStatus.succeeded
            )
        )
        .all()
    )
    
    if not successful_payments:
        return PaymentAnalyticsResponse(
            total_spent=0,
            total_spent_formatted="$0.00",
            payment_frequency=0.0,
            average_payment_amount=0.0,
            most_expensive_payment=None,
            most_frequent_checklist=None,
            spending_by_month=[],
            spending_by_checklist=[],
            payment_success_rate=0.0,
            total_access_days=0,
            average_access_duration=0.0,
        )
    
    # Calculate basic metrics
    total_spent = sum(p.amount_cents for p in successful_payments)
    average_payment_amount = total_spent / len(successful_payments)
    most_expensive_payment = max(successful_payments, key=lambda p: p.amount_cents)
    
    # Payment frequency (payments per month)
    if len(successful_payments) > 1:
        date_range = (max(p.created_at for p in successful_payments) - 
                      min(p.created_at for p in successful_payments)).days
        payment_frequency = (len(successful_payments) / date_range) * 30 if date_range > 0 else 0
    else:
        payment_frequency = 0.0
    
    # Payment success rate
    all_payments = db.query(Payment).filter(Payment.user_id == user_id).all()
    payment_success_rate = len(successful_payments) / len(all_payments) if all_payments else 0
    
    # Spending by month
    spending_by_month_query = (
        db.query(
            func.date_trunc('month', Payment.created_at).label('month'),
            func.sum(Payment.amount_cents).label('amount'),
            func.count(Payment.id).label('count'),
            func.avg(Payment.amount_cents).label('avg_amount'),
        )
        .filter(
            and_(
                Payment.user_id == user_id,
                Payment.status == PaymentStatus.succeeded
            )
        )
        .group_by(func.date_trunc('month', Payment.created_at))
        .order_by('month')
        .all()
    )
    
    spending_by_month = []
    for month, amount, count, avg_amount in spending_by_month_query:
        spending_by_month.append(MonthlySpending(
            month=month.strftime("%Y-%m"),
            amount_cents=amount or 0,
            amount_formatted=_format_currency(amount or 0),
            payment_count=count,
            average_amount=float(avg_amount or 0),
        ))
    
    # Spending by checklist
    spending_by_checklist_query = (
        db.query(
            Checklist.id,
            func.coalesce(ChecklistTranslation.title, f"Checklist v{Checklist.version}").label('title'),
            func.coalesce(ChecklistTranslation.description, "").label('description'),
            func.count(Payment.id).label('payment_count'),
            func.sum(Payment.amount_cents).label('total_amount'),
            func.avg(Payment.amount_cents).label('avg_amount'),
            func.max(Payment.created_at).label('last_payment'),
        )
        .join(Payment, Checklist.id == Payment.checklist_id)
        .outerjoin(ChecklistTranslation, Checklist.id == ChecklistTranslation.checklist_id)
        .filter(
            and_(
                Payment.user_id == user_id,
                Payment.status == PaymentStatus.succeeded
            )
        )
        .group_by(Checklist.id, ChecklistTranslation.title, ChecklistTranslation.description, Checklist.version)
        .order_by(desc('total_amount'))
        .limit(10)
        .all()
    )
    
    spending_by_checklist = []
    most_frequent_checklist_data = None
    max_payment_count = 0
    
    for cb in spending_by_checklist_query:
        checklist_stats = ChecklistPaymentStats(
            checklist_id=cb.id,
            checklist_title=cb.title,
            checklist_description=cb.description,
            total_payments=cb.payment_count,
            total_amount=cb.total_amount or 0,
            average_amount=float(cb.avg_amount or 0),
            last_payment_date=cb.last_payment,
            access_windows_granted=0,  # TODO: Calculate this
            is_most_purchased=False,
        )
        
        spending_by_checklist.append(checklist_stats)
        
        if cb.payment_count > max_payment_count:
            max_payment_count = cb.payment_count
            most_frequent_checklist_data = checklist_stats
    
    # Access metrics
    access_windows = (
        db.query(AccessWindow)
        .join(Payment, AccessWindow.payment_id == Payment.id)
        .filter(Payment.user_id == user_id)
        .all()
    )
    
    total_access_days = sum(
        (aw.expires_at - aw.activated_at).days + 1 for aw in access_windows
    )
    average_access_duration = total_access_days / len(access_windows) if access_windows else 0
    
    # Build most expensive payment record
    most_expensive_payment_record = None
    if most_expensive_payment:
        checklist = db.query(Checklist).filter(Checklist.id == most_expensive_payment.checklist_id).first()
        most_expensive_payment_record = PaymentRecord(
            id=most_expensive_payment.id,
            user_id=most_expensive_payment.user_id,
            checklist_id=most_expensive_payment.checklist_id,
            checklist_title=checklist.title if checklist else None,
            checklist_description=checklist.description if checklist else None,
            checklist_version=checklist.version if checklist else None,
            stripe_payment_intent_id=most_expensive_payment.stripe_payment_intent_id,
            amount_cents=most_expensive_payment.amount_cents,
            amount_formatted=_format_currency(most_expensive_payment.amount_cents),
            currency=most_expensive_payment.currency,
            status=most_expensive_payment.status,
            paid_at=most_expensive_payment.paid_at,
            created_at=most_expensive_payment.created_at,
            access_window_start=None,
            access_window_end=None,
            is_access_active=False,
            days_of_access=None,
        )
    
    return PaymentAnalyticsResponse(
        total_spent=total_spent,
        total_spent_formatted=_format_currency(total_spent),
        payment_frequency=payment_frequency,
        average_payment_amount=average_payment_amount,
        most_expensive_payment=most_expensive_payment_record,
        most_frequent_checklist=most_frequent_checklist_data,
        spending_by_month=spending_by_month,
        spending_by_checklist=spending_by_checklist,
        payment_success_rate=payment_success_rate,
        total_access_days=total_access_days,
        average_access_duration=average_access_duration,
    )
