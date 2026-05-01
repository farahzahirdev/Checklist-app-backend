"""API endpoints for assessment review operations."""
from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies.auth import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.models.assessment_review import (
    AssessmentReview, 
    AnswerReview, 
    ReviewStatus, 
    SuggestionType,
    ReviewHistory
)
from app.models.checklist import Checklist, ChecklistTranslation
from app.schemas.assessment_review import (
    AssessmentReviewCreate,
    AssessmentReviewUpdate,
    AssessmentReviewResponse,
    AnswerReviewCreate,
    AnswerReviewUpdate,
    AnswerReviewResponse,
    AssessmentAnswerListResponse,
    ReviewSummary,
    BulkAnswerReviewCreate,
    BulkAnswerReviewResponse,
)
from app.services.assessment_review import (
    get_assessment_for_review,
    get_assessment_answers_with_reviews,
    create_answer_review,
    update_answer_review,
    delete_answer_review,
    update_assessment_review,
    create_bulk_answer_reviews,
    get_review_summary,
    get_assessment_reviews_for_admin,
)
from app.utils.i18n import get_language_code

router = APIRouter(prefix="/admin/assessment-review", tags=["assessment-review"])


@router.get(
    "/summary",
    response_model=ReviewSummary,
    summary="Get Review Summary",
    description="Get summary statistics for assessment reviews.",
)
def get_review_summary_endpoint(
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> ReviewSummary:
    """Get review summary statistics."""
    return get_review_summary(db)


@router.get(
    "/assessments",
    response_model=List[AssessmentReviewResponse],
    summary="Get Assessment Reviews",
    description="Get list of assessment reviews for admin dashboard.",
)
def get_assessment_reviews(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by review status"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> List[AssessmentReviewResponse]:
    """Get assessment reviews for admin."""
    lang_code = get_language_code(request, db)
    return get_assessment_reviews_for_admin(db, status=status, skip=skip, limit=limit, lang_code=lang_code)


@router.get(
    "/assessment/{assessment_id}",
    response_model=AssessmentAnswerListResponse,
    summary="Get Assessment Answers for Review",
    description="Get all answers for an assessment along with any existing reviews.",
)
def get_assessment_answers(
    assessment_id: UUID,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AssessmentAnswerListResponse:
    """Get assessment answers for review."""
    lang_code = get_language_code(request, db)
    return get_assessment_answers_with_reviews(db, assessment_id, admin.id, lang_code)


@router.post(
    "/assessment/{assessment_id}/review",
    response_model=AssessmentReviewResponse,
    summary="Create or Update Assessment Review",
    description="Create or update overall assessment review.",
)
def create_or_update_assessment_review(
    assessment_id: UUID,
    review_data: AssessmentReviewUpdate,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AssessmentReviewResponse:
    """Create or update assessment review."""
    try:
        return update_assessment_review(db, assessment_id, admin.id, review_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/answer/{answer_id}/review",
    response_model=AnswerReviewResponse,
    summary="Create Answer Review",
    description="Create review for a specific answer.",
)
def create_answer_review_endpoint(
    answer_id: UUID,
    review_data: AnswerReviewCreate,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AnswerReviewResponse:
    """Create answer review."""
    try:
        # We need to get the assessment_id from the answer
        from app.models.assessment import AssessmentAnswer
        
        answer = db.query(AssessmentAnswer).filter(AssessmentAnswer.id == answer_id).first()
        if not answer:
            raise HTTPException(status_code=404, detail="Answer not found")
        
        return create_answer_review(db, answer.assessment_id, answer_id, admin.id, review_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put(
    "/answer-review/{review_id}",
    response_model=AnswerReviewResponse,
    summary="Update Answer Review",
    description="Update existing answer review.",
)
def update_answer_review_endpoint(
    review_id: UUID,
    review_data: AnswerReviewUpdate,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AnswerReviewResponse:
    """Update answer review."""
    try:
        return update_answer_review(db, review_id, admin.id, review_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/answer-review/{review_id}",
    summary="Delete Answer Review",
    description="Delete answer review.",
)
def delete_answer_review_endpoint(
    review_id: UUID,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> dict:
    """Delete answer review."""
    try:
        success = delete_answer_review(db, review_id, admin.id)
        return {"success": success, "message": "Review deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/assessment/{assessment_id}/bulk-reviews",
    response_model=BulkAnswerReviewResponse,
    summary="Create Bulk Answer Reviews",
    description="Create multiple answer reviews at once.",
)
def create_bulk_answer_reviews_endpoint(
    assessment_id: UUID,
    bulk_data: BulkAnswerReviewCreate,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> BulkAnswerReviewResponse:
    """Create bulk answer reviews."""
    try:
        return create_bulk_answer_reviews(db, assessment_id, admin.id, bulk_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/assessment/{assessment_id}/status",
    summary="Get Assessment Review Status",
    description="Get current review status for an assessment.",
)
def get_assessment_review_status(
    assessment_id: UUID,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> dict:
    """Get assessment review status."""
    from app.models.assessment_review import AssessmentReview
    
    review = db.query(AssessmentReview).filter(AssessmentReview.assessment_id == assessment_id).first()
    
    if not review:
        return {
            "assessment_id": assessment_id,
            "has_review": False,
            "status": "not_started",
            "review_id": None,
        }
    
    # Count answer reviews
    from app.models.assessment_review import AnswerReview
    
    answer_reviews_count = (
        db.scalar(
            select(func.count(AnswerReview.id))
            .filter(AnswerReview.assessment_review_id == review.id)
        ) or 0
    )
    
    action_required_count = (
        db.scalar(
            select(func.count(AnswerReview.id))
            .filter(
                AnswerReview.assessment_review_id == review.id,
                AnswerReview.is_action_required == True
            )
        ) or 0
    )
    
    return {
        "assessment_id": assessment_id,
        "has_review": True,
        "status": review.status,
        "review_id": review.id,
        "reviewer_id": review.reviewer_id,
        "answer_reviews_count": answer_reviews_count,
        "action_required_count": action_required_count,
        "reviewed_at": review.reviewed_at,
        "submitted_at": review.submitted_at,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


# Quick action endpoints for common review tasks

@router.post(
    "/assessment/{assessment_id}/quick-approve",
    summary="Quick Approve Assessment",
    description="Quickly approve assessment with minimal review.",
)
def quick_approve_assessment(
    assessment_id: UUID,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AssessmentReviewResponse:
    """Quick approve assessment."""
    review_data = AssessmentReviewUpdate(
        status="completed",
        summary_notes="Assessment approved via quick review.",
        recommendations="No major issues identified. Assessment meets requirements."
    )
    
    try:
        return update_assessment_review(db, assessment_id, admin.id, review_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/assessment/{assessment_id}/request-changes",
    summary="Request Changes",
    description="Request customer to make changes to assessment.",
)
def request_assessment_changes(
    request: Request,
    assessment_id: UUID,
    request_data: dict = {"reason": str, "required_changes": str},
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AssessmentReviewResponse:
    """Request changes to assessment."""
    review_data = AssessmentReviewUpdate(
        status="in_progress",
        summary_notes=f"Changes requested: {request_data.get('reason', 'No reason provided')}",
        improvement_areas=request_data.get("required_changes", "Please review and update assessment."),
        recommendations="Please address the identified issues and resubmit for review."
    )
    
    try:
        return update_assessment_review(db, assessment_id, admin.id, review_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/my-reviews",
    response_model=List[AssessmentReviewResponse],
    summary="Get My Reviews",
    description="Get reviews assigned to current user.",
)
def get_my_reviews(
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> List[AssessmentReviewResponse]:
    """Get reviews assigned to current user."""
    from app.models.assessment_review import AssessmentReview
    from app.models.assessment import Assessment
    from app.services.assessment_review import get_or_create_assessment_review
    from app.models.assessment_review import ReviewStatus
    
    # Get existing reviews
    existing_reviews = (
        db.query(AssessmentReview)
        .filter(AssessmentReview.reviewer_id == admin.id)
        .order_by(desc(AssessmentReview.updated_at))
        .all()
    )
    
    # Get submitted assessments that don't have reviews yet
    submitted_assessments = (
        db.query(Assessment)
        .filter(Assessment.status == 'submitted')
        .filter(~Assessment.id.in_([r.assessment_id for r in existing_reviews]))
        .order_by(desc(Assessment.updated_at))
        .all()
    )
    
    # Create reviews for submitted assessments
    for assessment in submitted_assessments:
        try:
            get_or_create_assessment_review(db, assessment.id, admin.id)
        except Exception:
            # Skip if there's an error creating review
            continue
    
    # Commit the new reviews
    db.commit()
    
    # Get all reviews again (including newly created ones) with related data
    all_reviews = (
        db.query(AssessmentReview)
        .options(
            joinedload(AssessmentReview.assessment)
            .joinedload(Assessment.user),
            joinedload(AssessmentReview.assessment)
            .joinedload(Assessment.checklist)
            .joinedload(Checklist.translations)
            .joinedload(ChecklistTranslation.language)
        )
        .filter(AssessmentReview.reviewer_id == admin.id)
        .order_by(desc(AssessmentReview.updated_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    # Build responses with proper data
    responses = []
    for review in all_reviews:
        response = AssessmentReviewResponse.model_validate(review, from_attributes=True)
        
        # Add assessment context data
        if review.assessment:
            response.customer_email = review.assessment.user.email if review.assessment.user else None
            response.customer_name = review.assessment.user.full_name if review.assessment.user else None
            response.checklist_title = next((t.title for t in review.assessment.checklist.translations if t.language.code == 'en'), None)
            response.checklist_version = review.assessment.checklist.version
            response.assessment_status = review.assessment.status
            response.submitted_at = review.assessment.updated_at
        
        responses.append(response)
    
    return responses


@router.get(
    "/answer-review/{review_id}/history",
    summary="Get Review History",
    description="Get change history for a specific review.",
)
def get_review_history(
    review_id: UUID,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get review history."""
    from app.models.assessment_review import AnswerReview, ReviewHistory
    from app.models.user import User
    from sqlalchemy.orm import joinedload
    
    # Get answer review to find assessment review
    answer_review = db.query(AnswerReview).filter(AnswerReview.id == review_id).first()
    if not answer_review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    # Get history with reviewer information
    history = (
        db.query(ReviewHistory)
        .options(joinedload(ReviewHistory.reviewer))
        .filter(ReviewHistory.assessment_review_id == answer_review.assessment_review_id)
        .order_by(desc(ReviewHistory.created_at))
        .all()
    )
    
    return [
        {
            "id": h.id,
            "action_type": h.action_type,
            "description": h.description,
            "previous_values": h.previous_values,
            "new_values": h.new_values,
            "created_at": h.created_at,
            "reviewer_id": h.reviewer_id,
            "reviewer_name": h.reviewer.email if h.reviewer else None,
            "reviewer_email": h.reviewer.email if h.reviewer else None,
        }
        for h in history
    ]
