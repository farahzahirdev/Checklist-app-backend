"""Service layer for assessment review operations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from sqlalchemy import func, select, and_, or_, desc
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.assessment import Assessment, AssessmentAnswer, AssessmentEvidenceFile, AssessmentStatus
from app.models.checklist import ChecklistTranslation
from app.models.assessment_review import (
    AssessmentReview, 
    AnswerReview, 
    ReviewStatus, 
    SuggestionType,
    ReviewHistory
)
from app.models.checklist import (
    Checklist, 
    ChecklistQuestion, 
    ChecklistSection,
    ChecklistSectionTranslation,
    ChecklistQuestionTranslation,
)
from app.models.user import User
from app.models.reference import Language
from app.utils.audit_logger import AuditLogger
from app.schemas.assessment_review import (
    AssessmentReviewCreate,
    AssessmentReviewUpdate,
    AssessmentReviewResponse,
    AnswerReviewCreate,
    AnswerReviewUpdate,
    AnswerReviewResponse,
    AnswerWithReview,
    AssessmentAnswerListResponse,
    ReviewSummary,
    BulkAnswerReviewCreate,
    BulkAnswerReviewResponse,
    BulkAnswerReviewResult,
    ReviewAnalytics,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _log_assessment_review_audit(
    db: Session,
    *,
    action: str,
    review_id: UUID,
    actor_user_id: UUID | None = None,
    target_user_id: UUID | None = None,
    changes_summary: str | None = None,
    after_data: dict | None = None,
) -> None:
    try:
        AuditLogger.log_assessment_review_action(
            db=db,
            action=action,
            review_id=review_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            changes_summary=changes_summary,
            after_data=after_data,
        )
    except Exception as e:
        print(f"Error creating audit log for assessment review {review_id}: {e}")


def get_assessment_for_review(
    db: Session, 
    assessment_id: UUID,
    company_id: UUID | None = None,
    lang_code: str = "en"
) -> Optional[Assessment]:
    """Get assessment with all related data for review."""
    
    assessment_query = (
        db.query(Assessment)
        .options(
            joinedload(Assessment.user),
            joinedload(Assessment.checklist)
            .joinedload(Checklist.translations)
            .joinedload(ChecklistTranslation.language),
            joinedload(Assessment.answers)
            .joinedload(AssessmentAnswer.question)
            .joinedload(ChecklistQuestion.translations)
            .joinedload(ChecklistQuestionTranslation.language),
            joinedload(Assessment.answers)
            .joinedload(AssessmentAnswer.question)
            .joinedload(ChecklistQuestion.section)
            .joinedload(ChecklistSection.translations)
            .joinedload(ChecklistSectionTranslation.language),
        )
        .filter(Assessment.id == assessment_id)
        .filter(Assessment.status == AssessmentStatus.submitted)  # Only submitted assessments
    )
    if company_id is not None:
        assessment_query = assessment_query.filter(Assessment.company_id == company_id)
    assessment = assessment_query.first()
    
    return assessment


def get_assessment_answers_with_reviews(
    db: Session, 
    assessment_id: UUID,
    company_id: UUID | None = None,
    reviewer_id: Optional[UUID] = None,
    lang_code: str = "en"
) -> AssessmentAnswerListResponse:
    """Get all assessment answers with their reviews."""
    
    # Get assessment with customer info
    assessment_query = (
        db.query(Assessment)
        .options(joinedload(Assessment.user))
        .options(
            joinedload(Assessment.checklist)
            .joinedload(Checklist.translations)
            .joinedload(ChecklistTranslation.language)
        )
        .filter(Assessment.id == assessment_id)
    )
    if company_id is not None:
        assessment_query = assessment_query.filter(Assessment.company_id == company_id)
    assessment = assessment_query.first()
    
    if not assessment:
        raise ValueError("Assessment not found")
    
    # Get all answers with question details
    answers_query = (
        db.query(AssessmentAnswer)
        .options(
            joinedload(AssessmentAnswer.question)
            .joinedload(ChecklistQuestion.translations)
            .joinedload(ChecklistQuestionTranslation.language),
            joinedload(AssessmentAnswer.question)
            .joinedload(ChecklistQuestion.section)
            .joinedload(ChecklistSection.translations)
            .joinedload(ChecklistSectionTranslation.language),
        )
        .filter(AssessmentAnswer.assessment_id == assessment_id)
    )
    
    answers = answers_query.all()
    
    # Get evidence files for all answers and questions
    evidence_files_query = (
        db.query(AssessmentEvidenceFile)
        .filter(
            AssessmentEvidenceFile.assessment_id == assessment_id,
            AssessmentEvidenceFile.deleted_at.is_(None)
        )
        .options(joinedload(AssessmentEvidenceFile.media))
    )
    evidence_files = evidence_files_query.all()
    
    # Group evidence files by answer_id and question_id
    evidence_by_answer = {}
    evidence_by_question = {}
    
    for evidence_file in evidence_files:
        evidence_data = {
            "id": str(evidence_file.id),
            "media_id": str(evidence_file.media_id),
            "filename": evidence_file.media.original_filename,
            "mime_type": evidence_file.media.mime_type,
            "file_size": evidence_file.media.file_size_bytes,
            "scan_status": evidence_file.media.scan_status,
            "encryption_status": evidence_file.media.encryption_status,
            "uploaded_at": evidence_file.uploaded_at.isoformat() if evidence_file.uploaded_at else None,
        }
        
        # Group by answer_id if present
        if evidence_file.answer_id:
            if evidence_file.answer_id not in evidence_by_answer:
                evidence_by_answer[evidence_file.answer_id] = []
            evidence_by_answer[evidence_file.answer_id].append(evidence_data)
        
        # Also group by question_id for files not linked to answers
        if evidence_file.question_id:
            if evidence_file.question_id not in evidence_by_question:
                evidence_by_question[evidence_file.question_id] = []
            evidence_by_question[evidence_file.question_id].append(evidence_data)
    
    # Sort answers in Python by section order then question order
    answers.sort(key=lambda a: (
        a.question.section.display_order if a.question.section else 0,
        a.question.display_order or 0
    ))
    
    # Get existing reviews
    reviews_query = (
        db.query(AnswerReview)
        .filter(AnswerReview.answer_id.in_([a.id for a in answers]))
    )
    
    if reviewer_id:
        reviews_query = reviews_query.filter(AnswerReview.reviewer_id == reviewer_id)
    
    reviews = reviews_query.all()
    reviews_by_answer = {review.answer_id: review for review in reviews}
    
    # Build response
    answer_with_reviews = []
    total_score = 0
    reviewed_count = 0
    action_required_count = 0
    
    for answer in answers:
        # Get translations
        question_translation = next(
            (t for t in answer.question.translations 
             if t.language.code == lang_code), 
            None
        )
        section_translation = next(
            (t for t in answer.question.section.translations 
             if t.language.code == lang_code), 
            None
        )
        
        question_text = question_translation.question_text if question_translation else answer.question.question_code
        explanation = question_translation.explanation if question_translation and question_translation.explanation else None
        expected_implementation = question_translation.expected_implementation if question_translation and question_translation.expected_implementation else None
        why_this_matters = question_translation.how_it_works if question_translation and question_translation.how_it_works else None
        legal_requirement_title = question_translation.legal_requirement_title if question_translation and question_translation.legal_requirement_title else None
        legal_requirement_description = question_translation.legal_requirement_description if question_translation and question_translation.legal_requirement_description else None
        audit_type = answer.question.audit_type if hasattr(answer.question, 'audit_type') else None
        section_name = section_translation.title if section_translation else answer.question.section.section_code
        
        # Get review if exists
        review = reviews_by_answer.get(answer.id)
        has_review = review is not None
        is_action_required = review.is_action_required if review else False
        review_priority = review.priority_level if review else 0
        
        if has_review:
            reviewed_count += 1
        if is_action_required:
            action_required_count += 1
        
        total_score += answer.answer_score
        
        answer_with_reviews.append(AnswerWithReview(
            answer_id=answer.id,
            # public `question_id` should be question code string per request
            question_id=answer.question.question_code,
            question_uuid=answer.question_id,
            question_text=question_text,
            explanation=explanation,
            audit_type=audit_type,
            why_this_matters=why_this_matters,
            legal_requirement_title=legal_requirement_title,
            legal_requirement_description=legal_requirement_description,
            expected_implementation=expected_implementation,
            section_code=answer.question.section.section_code,
            section_name=section_name,
            customer_answer=answer.answer.value if answer.answer else "Not answered",
            customer_score=answer.answer_score,
            weighted_priority=answer.weighted_priority.value if answer.weighted_priority else None,
            note_text=answer.note_text,
            answered_at=answer.answered_at,
            evidence_files=(
                evidence_by_answer.get(answer.id, []) + 
                evidence_by_question.get(answer.question_id, [])
            ),
            review=AnswerReviewResponse.from_orm(review) if review else None,
            has_review=has_review,
            is_action_required=is_action_required,
            review_priority=review_priority,
        ))
    
    # Calculate statistics
    average_score = total_score / len(answers) if answers else 0
    # Get checklist title translation
    checklist_translation = next(
        (t for t in assessment.checklist.translations 
         if t.language.code == lang_code), 
        None
    )
    
    completion_percentage = assessment.completion_percent or 0
    
    return AssessmentAnswerListResponse(
        assessment_id=assessment_id,
        customer_email=assessment.user.email,
        customer_name=assessment.user.email,
        checklist_title=checklist_translation.title if checklist_translation else f"Checklist v{assessment.checklist.version}",
        checklist_version=f"v{assessment.checklist.version}",
        assessment_status=assessment.status.value,
        submitted_at=assessment.submitted_at,
        answers=answer_with_reviews,
        total_answers=len(answers),
        reviewed_answers=reviewed_count,
        action_required_answers=action_required_count,
        average_score=average_score,
        completion_percentage=completion_percentage,
        generated_at=_now_utc(),
    )


def get_or_create_assessment_review(
    db: Session, 
    assessment_id: UUID,
    reviewer_id: UUID
) -> AssessmentReview:
    """Get existing assessment review or create new one."""
    
    # Try to get existing review
    review = (
        db.query(AssessmentReview)
        .filter(AssessmentReview.assessment_id == assessment_id)
        .first()
    )
    
    if not review:
        # Create new review
        review = AssessmentReview(
            assessment_id=assessment_id,
            reviewer_id=reviewer_id,
            status=ReviewStatus.PENDING,
        )
        db.add(review)
        db.flush()
        
        # Add history entry
        history = ReviewHistory(
            assessment_review_id=review.id,
            reviewer_id=reviewer_id,
            action_type="created",
            description="Assessment review created",
        )
        db.add(history)
        db.commit()

        _log_assessment_review_audit(
            db,
            action="assessment_review_create",
            review_id=review.id,
            actor_user_id=reviewer_id,
            changes_summary=f"Created assessment review for assessment {assessment_id}",
            after_data={"assessment_id": str(assessment_id), "status": review.status},
        )
    
    return review


def create_answer_review(
    db: Session,
    assessment_id: UUID,
    answer_id: UUID,
    reviewer_id: UUID,
    review_data: AnswerReviewCreate
) -> AnswerReviewResponse:
    """Create review for a specific answer."""
    
    # Verify answer belongs to assessment
    answer = (
        db.query(AssessmentAnswer)
        .filter(
            AssessmentAnswer.id == answer_id,
            AssessmentAnswer.assessment_id == assessment_id
        )
        .first()
    )
    
    if not answer:
        raise ValueError("Answer not found or doesn't belong to assessment")
    
    # Check if review already exists
    existing_review = (
        db.query(AnswerReview)
        .filter(AnswerReview.answer_id == answer_id)
        .first()
    )
    
    if existing_review:
        raise ValueError("Review already exists for this answer")
    
    # Get or create assessment review
    assessment_review = get_or_create_assessment_review(db, assessment_id, reviewer_id)
    
    # Create answer review
    review = AnswerReview(
        assessment_review_id=assessment_review.id,
        answer_id=answer_id,
        reviewer_id=reviewer_id,
        suggestion_type=review_data.suggestion_type,
        suggestion_text=review_data.suggestion_text,
        reference_materials=review_data.reference_materials,
        is_action_required=review_data.is_action_required,
        priority_level=review_data.priority_level,
        score_adjustment=review_data.score_adjustment,
    )
    
    db.add(review)
    
    # Update assessment review status if needed
    if assessment_review.status == ReviewStatus.PENDING:
        assessment_review.status = ReviewStatus.IN_PROGRESS
    
    # Add history entry
    history = ReviewHistory(
        assessment_review_id=assessment_review.id,
        reviewer_id=reviewer_id,
        action_type="answer_review_created",
        description=f"Review created for answer {answer_id}",
    )
    db.add(history)
    
    db.commit()

    _log_assessment_review_audit(
        db,
        action="answer_review_create",
        review_id=assessment_review.id,
        actor_user_id=reviewer_id,
        changes_summary=f"Created answer review for answer {answer_id}",
        after_data={"answer_id": str(answer_id), "suggestion_type": str(review.suggestion_type)},
    )
    
    return AnswerReviewResponse.from_orm(review)


def update_answer_review(
    db: Session,
    review_id: UUID,
    reviewer_id: UUID,
    review_data: AnswerReviewUpdate
) -> AnswerReviewResponse:
    """Update existing answer review."""
    
    review = (
        db.query(AnswerReview)
        .filter(AnswerReview.id == review_id)
        .first()
    )
    
    if not review:
        raise ValueError("Review not found")
    
    # Store previous values for history
    previous_values = {
        "suggestion_type": review.suggestion_type,
        "suggestion_text": review.suggestion_text,
        "reference_materials": review.reference_materials,
        "is_action_required": review.is_action_required,
        "priority_level": review.priority_level,
        "score_adjustment": review.score_adjustment,
    }
    
    # Update fields
    update_data = review_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(review, field, value)
    
    # Add history entry
    history = ReviewHistory(
        assessment_review_id=review.assessment_review_id,
        reviewer_id=reviewer_id,
        action_type="answer_review_updated",
        description=f"Review updated for answer {review.answer_id}",
        previous_values=str(previous_values),
        new_values=str(update_data),
    )
    db.add(history)
    
    db.commit()

    _log_assessment_review_audit(
        db,
        action="answer_review_update",
        review_id=review.assessment_review_id,
        actor_user_id=reviewer_id,
        changes_summary=f"Updated answer review for answer {review.answer_id}",
        after_data={"answer_id": str(review.answer_id)},
    )
    
    return AnswerReviewResponse.from_orm(review)


def delete_answer_review(
    db: Session,
    review_id: UUID,
    reviewer_id: UUID
) -> bool:
    """Delete answer review."""
    
    review = (
        db.query(AnswerReview)
        .filter(AnswerReview.id == review_id)
        .first()
    )
    
    if not review:
        raise ValueError("Review not found")
    
    assessment_review_id = review.assessment_review_id
    answer_id = review.answer_id
    
    # Add history entry
    history = ReviewHistory(
        assessment_review_id=assessment_review_id,
        reviewer_id=reviewer_id,
        action_type="answer_review_deleted",
        description=f"Review deleted for answer {answer_id}",
    )
    db.add(history)
    
    # Delete review
    db.delete(review)
    db.commit()

    _log_assessment_review_audit(
        db,
        action="answer_review_delete",
        review_id=assessment_review_id,
        actor_user_id=reviewer_id,
        changes_summary=f"Deleted answer review for answer {answer_id}",
        after_data={"answer_id": str(answer_id)},
    )
    
    return True


def update_assessment_review(
    db: Session,
    assessment_id: UUID,
    reviewer_id: UUID,
    review_data: AssessmentReviewUpdate
) -> AssessmentReviewResponse:
    """Update overall assessment review."""
    
    review = get_or_create_assessment_review(db, assessment_id, reviewer_id)
    
    # Store previous values for history
    previous_values = {
        "status": review.status,
        "overall_score": review.overall_score,
        "max_score": review.max_score,
        "completion_percentage": review.completion_percentage,
        "summary_notes": review.summary_notes,
        "strengths": review.strengths,
        "improvement_areas": review.improvement_areas,
        "recommendations": review.recommendations,
    }
    
    # Update fields
    update_data = review_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(review, field, value)
    
    # Set reviewed_at if first time updating
    if not review.reviewed_at and any(update_data.values()):
        review.reviewed_at = _now_utc()
    
    # Set submitted_at if status is completed
    if update_data.get("status") == ReviewStatus.COMPLETED and not review.submitted_at:
        review.submitted_at = _now_utc()
    
    # Add history entry
    history = ReviewHistory(
        assessment_review_id=review.id,
        reviewer_id=reviewer_id,
        action_type="assessment_review_updated",
        description="Assessment review updated",
        previous_values=str(previous_values),
        new_values=str(update_data),
    )
    db.add(history)
    
    db.commit()

    _log_assessment_review_audit(
        db,
        action="assessment_review_submit" if update_data.get("status") == ReviewStatus.COMPLETED else "assessment_review_update",
        review_id=review.id,
        actor_user_id=reviewer_id,
        changes_summary="Assessment review completed" if update_data.get("status") == ReviewStatus.COMPLETED else "Assessment review updated",
        after_data={"assessment_id": str(assessment_id), "status": str(review.status)},
    )
    
    # If the assessment review was completed, start the report review flow for the generated draft
    try:
        if update_data.get("status") == ReviewStatus.COMPLETED:
            # Find any report for this assessment and mark it under review by this reviewer
            from sqlalchemy import select
            from app.models.report import Report
            from app.models.user import User as UserModel
            from app.schemas.report import ReviewActionRequest
            from app.services.report import start_review

            report = db.scalar(select(Report).where(Report.assessment_id == assessment_id))
            reviewer_user = db.get(UserModel, reviewer_id)
            if report and reviewer_user:
                payload = ReviewActionRequest(note="Assessment review completed; starting report review")
                start_review(db, report_id=report.id, actor=reviewer_user, payload=payload)
    except Exception:
        # Do not fail the review update if report start fails; log could be added here.
        db.rollback()
        pass

    db.refresh(review)

    return AssessmentReviewResponse.from_orm(review)


def create_bulk_answer_reviews(
    db: Session,
    assessment_id: UUID,
    reviewer_id: UUID,
    bulk_data: BulkAnswerReviewCreate
) -> BulkAnswerReviewResponse:
    """Create multiple answer reviews at once."""
    
    results = []
    success_count = 0
    failure_count = 0
    
    # Get or create assessment review
    assessment_review = get_or_create_assessment_review(db, assessment_id, reviewer_id)
    
    # Update assessment review status if needed
    if assessment_review.status == ReviewStatus.PENDING:
        assessment_review.status = ReviewStatus.IN_PROGRESS
    
    # Add overall assessment notes if provided
    if bulk_data.assessment_notes:
        assessment_review.summary_notes = bulk_data.assessment_notes
    
    for review_data in bulk_data.answer_reviews:
        try:
            # Verify answer belongs to assessment
            answer = (
                db.query(AssessmentAnswer)
                .filter(
                    AssessmentAnswer.id == review_data.answer_id,
                    AssessmentAnswer.assessment_id == assessment_id
                )
                .first()
            )
            
            if not answer:
                results.append(BulkAnswerReviewResult(
                    answer_id=review_data.answer_id,
                    success=False,
                    message="Answer not found or doesn't belong to assessment",
                ))
                failure_count += 1
                continue
            
            # Check if review already exists
            existing_review = (
                db.query(AnswerReview)
                .filter(AnswerReview.answer_id == review_data.answer_id)
                .first()
            )
            
            if existing_review:
                results.append(BulkAnswerReviewResult(
                    answer_id=review_data.answer_id,
                    success=False,
                    message="Review already exists for this answer",
                ))
                failure_count += 1
                continue
            
            # Create answer review
            review = AnswerReview(
                assessment_review_id=assessment_review.id,
                answer_id=review_data.answer_id,
                reviewer_id=reviewer_id,
                suggestion_type=review_data.suggestion_type,
                suggestion_text=review_data.suggestion_text,
                reference_materials=review_data.reference_materials,
                is_action_required=review_data.is_action_required,
                priority_level=review_data.priority_level,
                score_adjustment=review_data.score_adjustment,
            )
            
            db.add(review)
            
            # Add history entry
            history = ReviewHistory(
                assessment_review_id=assessment_review.id,
                reviewer_id=reviewer_id,
                action_type="answer_review_created",
                description=f"Bulk review created for answer {review_data.answer_id}",
            )
            db.add(history)
            
            results.append(BulkAnswerReviewResult(
                answer_id=review_data.answer_id,
                success=True,
                message="Review created successfully",
                review_id=review.id,
            ))
            success_count += 1
            
        except Exception as e:
            failure_count += 1
            results.append(BulkAnswerReviewResult(
                answer_id=review_data.answer_id,
                success=False,
                message=str(e),
            ))
    
    # Commit all changes
    db.commit()

    if success_count > 0:
        _log_assessment_review_audit(
            db,
            action="answer_review_create",
            review_id=assessment_review.id,
            actor_user_id=reviewer_id,
            changes_summary=f"Created {success_count} answer reviews for assessment {assessment_id}",
            after_data={"assessment_id": str(assessment_id), "success_count": success_count, "failure_count": failure_count},
        )
    
    return BulkAnswerReviewResponse(
        success_count=success_count,
        failure_count=failure_count,
        results=results,
        assessment_review_id=assessment_review.id,
    )


def get_review_summary(db: Session, company_id: UUID | None = None) -> ReviewSummary:
    """Get summary statistics for reviews."""
    
    # Assessment review counts
    pending_query = select(func.count(AssessmentReview.id)).join(Assessment, Assessment.id == AssessmentReview.assessment_id)
    if company_id is not None:
        pending_query = pending_query.filter(Assessment.company_id == company_id)
    pending_count = db.scalar(pending_query.filter(AssessmentReview.status == ReviewStatus.PENDING)) or 0
    
    in_progress_query = select(func.count(AssessmentReview.id)).join(Assessment, Assessment.id == AssessmentReview.assessment_id)
    if company_id is not None:
        in_progress_query = in_progress_query.filter(Assessment.company_id == company_id)
    in_progress_count = db.scalar(in_progress_query.filter(AssessmentReview.status == ReviewStatus.IN_PROGRESS)) or 0
    
    completed_query = select(func.count(AssessmentReview.id)).join(Assessment, Assessment.id == AssessmentReview.assessment_id)
    if company_id is not None:
        completed_query = completed_query.filter(Assessment.company_id == company_id)
    completed_count = db.scalar(completed_query.filter(AssessmentReview.status == ReviewStatus.COMPLETED)) or 0
    
    # Answer review counts
    total_answer_reviews = db.scalar(select(func.count(AnswerReview.id))) or 0
    if company_id is not None:
        total_answer_reviews = db.scalar(
            select(func.count(AnswerReview.id))
            .join(AssessmentReview, AssessmentReview.id == AnswerReview.assessment_review_id)
            .join(Assessment, Assessment.id == AssessmentReview.assessment_id)
            .where(Assessment.company_id == company_id)
        ) or 0
    
    total_action_required = db.scalar(select(func.count(AnswerReview.id)).filter(AnswerReview.is_action_required == True)) or 0
    if company_id is not None:
        total_action_required = db.scalar(
            select(func.count(AnswerReview.id))
            .join(AssessmentReview, AssessmentReview.id == AnswerReview.assessment_review_id)
            .join(Assessment, Assessment.id == AssessmentReview.assessment_id)
            .where(Assessment.company_id == company_id, AnswerReview.is_action_required == True)
        ) or 0
    
    # Recent reviews
    recent_reviews = (
        db.query(AssessmentReview)
        .options(joinedload(AssessmentReview.assessment).joinedload(Assessment.user))
        .order_by(desc(AssessmentReview.created_at))
        .limit(5)
        .all()
    )
    
    recent_review_responses = [AssessmentReviewResponse.from_orm(r) for r in recent_reviews]
    
    return ReviewSummary(
        total_assessments_pending_review=pending_count,
        total_assessments_in_progress=in_progress_count,
        total_assessments_completed=completed_count,
        total_answer_reviews=total_answer_reviews,
        total_action_required=total_action_required,
        average_review_time_hours=None,  # Would need more complex calculation
        recent_reviews=recent_review_responses,
    )


def get_assessment_reviews_for_admin(
    db: Session,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    company_id: UUID | None = None,
    lang_code: str = "en"
) -> List[AssessmentReviewResponse]:
    """Get assessment reviews for admin dashboard."""
    
    query = (
        db.query(AssessmentReview)
        .options(
            joinedload(AssessmentReview.assessment)
            .joinedload(Assessment.user),
            joinedload(AssessmentReview.assessment)
            .joinedload(Assessment.checklist)
            .joinedload(Checklist.translations)
            .joinedload(ChecklistTranslation.language),
        )
    )
    
    if status:
        query = query.filter(AssessmentReview.status == status)
    if company_id is not None:
        query = query.filter(Assessment.company_id == company_id)
    
    reviews = (
        query.order_by(desc(AssessmentReview.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    responses = []
    for r in reviews:
        # Create response using Pydantic model with from_attributes=True
        response = AssessmentReviewResponse.model_validate(r, from_attributes=True)
        
        # Populate additional context fields
        if r.assessment:
            response.customer_email = r.assessment.user.email if r.assessment.user else None
            response.customer_name = r.assessment.user.email if r.assessment.user else None
            response.assessment_status = r.assessment.status.value if r.assessment.status else None
            response.submitted_at = r.assessment.submitted_at
            
            # Get checklist title
            if r.assessment.checklist and r.assessment.checklist.translations:
                checklist_translation = next(
                    (t for t in r.assessment.checklist.translations 
                     if t.language.code == lang_code), 
                    None
                )
                response.checklist_title = checklist_translation.title if checklist_translation else f"Checklist v{r.assessment.checklist.version}"
                response.checklist_version = f"v{r.assessment.checklist.version}"
        
        responses.append(response)
    
    return responses
