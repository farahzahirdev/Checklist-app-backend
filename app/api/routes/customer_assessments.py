"""API endpoints for customer multi-assessment management."""
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.assessment import AssessmentStatus
from app.models.user import UserRole
from app.schemas.customer_assessments import (
    AssessmentSummary,
    AssessmentDetail,
    AssessmentProgress,
    CustomerAssessmentListResponse,
    CustomerAssessmentDashboardResponse,
    AssessmentActionRequest,
    AssessmentActionResponse,
    BulkAssessmentRequest,
    BulkAssessmentResponse,
    AssessmentAnalytics,
    AssessmentComparison,
)
from app.services.customer_assessments import (
    get_customer_assessments,
    get_assessment_detail,
    get_assessment_progress,
    get_customer_dashboard_enhanced,
    perform_assessment_action,
    perform_bulk_assessment_action,
    get_assessment_analytics,
)
from app.utils.i18n import get_language_code

router = APIRouter(prefix="/customer/assessments", tags=["customer-assessments"])


@router.get(
    "/",
    response_model=CustomerAssessmentListResponse,
    summary="List Customer Assessments",
    description="Get a paginated list of customer's assessments with filtering and sorting options.",
)
def list_customer_assessments(
    request: Request,
    status: Optional[list[AssessmentStatus]] = Query(None, description="Filter by assessment status"),
    checklist_type: Optional[list[str]] = Query(None, description="Filter by checklist type codes"),
    search: Optional[str] = Query(None, description="Search in checklist titles and types"),
    sort_by: str = Query("updated_at", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomerAssessmentListResponse:
    """Get customer's assessments with filtering and sorting."""
    lang_code = get_language_code(request, db)
    
    return get_customer_assessments(
        db=db,
        user_id=current_user.id,
        status_filter=status,
        checklist_type_filter=checklist_type,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
        lang_code=lang_code,
    )


@router.get(
    "/dashboard",
    response_model=CustomerAssessmentDashboardResponse,
    summary="Enhanced Customer Dashboard",
    description="Get comprehensive dashboard with assessment summaries, quick actions, and available checklists.",
)
def get_customer_assessment_dashboard(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomerAssessmentDashboardResponse:
    """Get enhanced customer dashboard."""
    lang_code = get_language_code(request, db)
    
    return get_customer_dashboard_enhanced(
        db=db,
        user_id=current_user.id,
        lang_code=lang_code,
    )


@router.get(
    "/{assessment_id}",
    response_model=AssessmentDetail,
    summary="Get Assessment Detail",
    description="Get detailed information about a specific assessment including progress tracking.",
)
def get_assessment_details(
    assessment_id: UUID,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentDetail:
    """Get detailed assessment information."""
    lang_code = get_language_code(request, db)
    
    try:
        return get_assessment_detail(
            db=db,
            user_id=current_user.id,
            assessment_id=assessment_id,
            lang_code=lang_code,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{assessment_id}/progress",
    response_model=AssessmentProgress,
    summary="Get Assessment Progress",
    description="Get detailed progress tracking for an assessment including section-by-section breakdown.",
)
def get_assessment_progress_endpoint(
    assessment_id: UUID,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentProgress:
    """Get assessment progress details."""
    lang_code = get_language_code(request, db)
    
    try:
        return get_assessment_progress(
            db=db,
            user_id=current_user.id,
            assessment_id=assessment_id,
            lang_code=lang_code,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{assessment_id}/action",
    response_model=AssessmentActionResponse,
    summary="Perform Assessment Action",
    description="Perform actions on an assessment such as pause, resume, extend expiry, or archive.",
)
def perform_assessment_action_endpoint(
    assessment_id: UUID,
    request: AssessmentActionRequest,
    request_obj: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentActionResponse:
    """Perform an action on an assessment."""
    try:
        return perform_assessment_action(
            db=db,
            user_id=current_user.id,
            assessment_id=assessment_id,
            action=request.action,
            reason=request.reason,
            metadata=request.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/bulk-action",
    response_model=BulkAssessmentResponse,
    summary="Perform Bulk Assessment Action",
    description="Perform actions on multiple assessments at once.",
)
def perform_bulk_assessment_action_endpoint(
    request: BulkAssessmentRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BulkAssessmentResponse:
    """Perform bulk actions on assessments."""
    try:
        return perform_bulk_assessment_action(
            db=db,
            user_id=current_user.id,
            assessment_ids=request.assessment_ids,
            action=request.action,
            parameters=request.parameters,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/analytics/performance",
    response_model=AssessmentAnalytics,
    summary="Get Assessment Analytics",
    description="Get analytics and insights about assessment performance and activity.",
)
def get_assessment_analytics_endpoint(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentAnalytics:
    """Get assessment analytics."""
    lang_code = get_language_code(request, db)
    
    return get_assessment_analytics(
        db=db,
        user_id=current_user.id,
        lang_code=lang_code,
    )


@router.get(
    "/compare",
    response_model=AssessmentComparison,
    summary="Compare Assessments",
    description="Compare multiple assessments to identify patterns and insights.",
)
def compare_assessments(
    request: Request,
    assessment_ids: list[UUID] = Query(..., description="List of assessment IDs to compare"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentComparison:
    """Compare multiple assessments."""
    # This is a placeholder implementation
    # In a real implementation, this would fetch the assessments and perform comparison analysis
    
    lang_code = get_language_code(request, db)
    
    # Fetch assessment summaries
    assessments = []
    for assessment_id in assessment_ids:
        try:
            detail = get_assessment_detail(
                db=db,
                user_id=current_user.id,
                assessment_id=assessment_id,
                lang_code=lang_code,
            )
            # Convert to summary format
            assessments.append(AssessmentSummary(
                id=detail.id,
                checklist_id=detail.checklist_id,
                checklist_title=detail.checklist_title,
                checklist_type_code=detail.checklist_type_code,
                checklist_version=detail.checklist_version,
                status=detail.status,
                completion_percent=detail.completion_percent,
                started_at=detail.started_at,
                submitted_at=detail.submitted_at,
                expires_at=detail.expires_at,
                days_until_expiry=detail.days_until_expiry,
                has_report=bool(detail.report_id),
                report_status=detail.report_status,
                last_activity=None,  # Would need to be calculated
            ))
        except ValueError:
            # Skip assessments that don't exist or don't belong to user
            continue
    
    if not assessments:
        raise HTTPException(status_code=404, detail="No valid assessments found for comparison")
    
    # Placeholder comparison metrics
    comparison_metrics = {
        "avg_completion_percent": sum(a.completion_percent for a in assessments) / len(assessments),
        "total_questions_answered": sum(a.answered_questions for a in assessments if hasattr(a, 'answered_questions')),
        "diversity_score": len(set(a.checklist_type_code for a in assessments)),
    }
    
    # Placeholder insights and recommendations
    insights = [
        "You show consistent progress across different checklist types",
        "Completion rates are above average",
    ]
    
    recommendations = [
        "Focus on completing assessments with higher completion percentages first",
        "Consider starting assessments in checklist types you haven't tried yet",
    ]
    
    return AssessmentComparison(
        assessments=assessments,
        comparison_metrics=comparison_metrics,
        insights=insights,
        recommendations=recommendations,
        generated_at=request.headers.get("date", "2024-01-01T00:00:00Z"),
    )


# Quick action endpoints for common tasks

@router.post(
    "/quick-action/resume/{assessment_id}",
    response_model=AssessmentActionResponse,
    summary="Quick Resume Assessment",
    description="Quickly resume an assessment.",
)
def quick_resume_assessment(
    assessment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentActionResponse:
    """Quick resume assessment."""
    try:
        return perform_assessment_action(
            db=db,
            user_id=current_user.id,
            assessment_id=assessment_id,
            action="resume",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/quick-action/extend/{assessment_id}",
    response_model=AssessmentActionResponse,
    summary="Quick Extend Assessment",
    description="Quickly extend assessment expiry by 7 days.",
)
def quick_extend_assessment(
    assessment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentActionResponse:
    """Quick extend assessment."""
    try:
        return perform_assessment_action(
            db=db,
            user_id=current_user.id,
            assessment_id=assessment_id,
            action="extend",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Utility endpoints

@router.get(
    "/summary/stats",
    summary="Get Assessment Statistics",
    description="Get quick statistics about assessments including review status.",
)
def get_assessment_statistics(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get quick assessment statistics with review status."""
    from app.models.assessment import Assessment
    from app.models.assessment_review import AssessmentReview
    
    stats = {}
    
    # Total assessments
    stats["total"] = (
        db.scalar(
            select(func.count(Assessment.id)).where(Assessment.user_id == current_user.id)
        ) or 0
    )
    
    # By status
    for status in AssessmentStatus:
        stats[f"status_{status.value}"] = (
            db.scalar(
                select(func.count(Assessment.id)).where(
                    Assessment.user_id == current_user.id,
                    Assessment.status == status,
                )
            ) or 0
        )
    
    # Review status for submitted assessments
    submitted_assessments = (
        db.execute(
            select(Assessment.id, AssessmentReview.status)
            .join(AssessmentReview, Assessment.id == AssessmentReview.assessment_id, isouter=True)
            .where(Assessment.user_id == current_user.id, Assessment.status == AssessmentStatus.submitted)
        ).all()
    )
    
    # Count by review status
    review_stats = {
        "pending": 0,
        "in_progress": 0, 
        "completed": 0,
        "rejected": 0,
        "changes_requested": 0,
        "not_reviewed": 0  # Submitted but no review created yet
    }
    
    for assessment_id, review_status in submitted_assessments:
        if review_status:
            if review_status in review_stats:
                review_stats[review_status] += 1
        else:
            review_stats["not_reviewed"] += 1
    
    # Add review stats to main stats
    stats.update({f"review_{k}": v for k, v in review_stats.items()})
    
    # Expiring soon (within 7 days)
    from datetime import timedelta, timezone
    seven_days_from_now = datetime.now(timezone.utc) + timedelta(days=7)
    
    stats["expiring_soon"] = (
        db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.user_id == current_user.id,
                Assessment.status.in_([AssessmentStatus.not_started, AssessmentStatus.in_progress]),
                Assessment.expires_at <= seven_days_from_now,
            )
        ) or 0
    )
    
    return stats


@router.get(
    "/review-status",
    summary="Get Assessment Review Status",
    description="Get detailed review status information for submitted assessments.",
)
def get_assessment_review_status(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get detailed review status for customer's submitted assessments."""
    from app.models.assessment import Assessment
    from app.models.assessment_review import AssessmentReview
    
    # Get submitted assessments with their review details
    submitted_assessments = (
        db.execute(
            select(
                Assessment.id,
                Assessment.submitted_at,
                AssessmentReview.status.label("review_status"),
                AssessmentReview.reviewed_at,
                AssessmentReview.submitted_at.label("review_submitted_at"),
                AssessmentReview.overall_score,
                AssessmentReview.reviewer_id
            )
            .join(AssessmentReview, Assessment.id == AssessmentReview.assessment_id, isouter=True)
            .where(Assessment.user_id == current_user.id, Assessment.status == AssessmentStatus.submitted)
            .order_by(Assessment.submitted_at.desc())
        ).all()
    )
    
    # Format the response
    assessments = []
    for assessment in submitted_assessments:
        review_status = assessment.review_status or "not_reviewed"
        
        assessments.append({
            "assessment_id": str(assessment.id),
            "submitted_at": assessment.submitted_at.isoformat() if assessment.submitted_at else None,
            "review_status": review_status,
            "reviewed_at": assessment.reviewed_at.isoformat() if assessment.reviewed_at else None,
            "review_submitted_at": assessment.review_submitted_at.isoformat() if assessment.review_submitted_at else None,
            "overall_score": assessment.overall_score,
            "has_reviewer": assessment.reviewer_id is not None
        })
    
    # Summary statistics
    total_submitted = len(assessments)
    status_counts = {}
    for assessment in assessments:
        status = assessment["review_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return {
        "total_submitted": total_submitted,
        "status_breakdown": status_counts,
        "assessments": assessments
    }
