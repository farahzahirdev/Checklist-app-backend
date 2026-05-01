from __future__ import annotations

import uuid
import re
from sqlalchemy import asc, case, desc, func, or_, select, delete, update
from sqlalchemy.orm import Session
from app.models.checklist import (
    Checklist,
    ChecklistQuestion,
    ChecklistQuestionAnswerOption,
    ChecklistQuestionTranslation,
    ChecklistSection,
    ChecklistSectionTranslation,
    ChecklistStatus,
    ChecklistTranslation,
    ChecklistType,
    SeverityLevel,
)
from app.models.assessment import Assessment
from app.models.reference import Language
from app.models.user import User
from app.services.stripe_products import create_stripe_product_for_checklist, get_stripe_price_for_checklist
from app.utils.audit_logger import AuditLogger
from app.schemas.admin_checklist import (
    AdminChecklistCreateRequest,
    AdminChecklistResponse,
    AdminChecklistUpdateRequest,
    AdminQuestionCreateRequest,
    AdminQuestionUpdateRequest,
    AdminQuestionResponse,
    AdminSectionCreateRequest,
    AdminSectionReorderRequest,
    AdminSectionUpdateRequest,
    AdminSectionResponse,
    AdminStripeInfo,
    EvidenceRuleResponse,
    PublishChecklistRequest,
)

DEFAULT_ALLOWED_MIME_TYPES = ["application/pdf", "image/png", "image/jpeg"]
DEFAULT_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_QUESTION_POINTS = 1
DEFAULT_ANSWER_LOGIC = "answer_only"


def _generate_unique_checklist_type_code(title: str) -> str:
    """Generate a unique checklist type code from title"""
    # Remove special characters and convert to lowercase
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', title).strip()
    words = clean_title.split()
    
    # Take first 3 words and create code
    if len(words) >= 3:
        code = '_'.join(words[:3]).lower()
    elif len(words) == 2:
        code = '_'.join(words).lower()
    elif len(words) == 1:
        code = words[0].lower()
    else:
        code = "checklist"
    
    # Add random suffix for uniqueness
    suffix = uuid.uuid4().hex[:6]
    return f"{code}_{suffix}"

def _get_or_create_unique_checklist_type(db: Session, title: str, description: str) -> ChecklistType:
    """Get or create a unique checklist type based on title"""
    # Generate unique code
    unique_code = _generate_unique_checklist_type_code(title)
    
    # Check if type with this code already exists (unlikely but possible)
    checklist_type = db.scalar(select(ChecklistType).where(ChecklistType.code == unique_code))
    if checklist_type is None:
        checklist_type = ChecklistType(
            code=unique_code,
            name=title,
            description=description,
            is_active=True,
        )
        db.add(checklist_type)
        db.flush()
    
    return checklist_type

def _ensure_default_checklist_type(db: Session) -> ChecklistType:
    checklist_type = db.scalar(select(ChecklistType).where(ChecklistType.code == "compliance"))
    if checklist_type is None:
        checklist_type = ChecklistType(code="compliance", name="Compliance", description="Default compliance type", is_active=True)
        db.add(checklist_type)
        db.flush()
    return checklist_type


def _format_version(version: int) -> str:
    return f"v{version}.0"


def _to_checklist_response(checklist: Checklist, db: Session) -> AdminChecklistResponse:
    # Get translation for title/description
    translation = None
    if hasattr(checklist, 'translations'):
        # If relationship is loaded
        translation = next(iter(checklist.translations), None)
    else:
        # Fallback: query translation
        from app.models.checklist import ChecklistTranslation
        translation = db.query(ChecklistTranslation).filter_by(checklist_id=checklist.id).first()

    title = translation.title if translation else f"Checklist v{checklist.version}"
    # Get ChecklistType for description
    checklist_type = getattr(checklist, "checklist_type", None)
    if not checklist_type:
        from app.models.checklist import ChecklistType
        checklist_type = db.query(ChecklistType).filter_by(id=checklist.checklist_type_id).first()
    decree = (translation.description if translation and translation.description else (checklist_type.description if checklist_type else title))
    
    # Get Stripe information
    stripe_info = AdminStripeInfo()
    if checklist.stripe_product_id:
        stripe_info.product_id = checklist.stripe_product_id
        
        # Try to get price information
        if db is not None:
            try:
                price_data = get_stripe_price_for_checklist(db, checklist_id=checklist.id)
                if price_data:
                    stripe_info.price_id = price_data["price_id"]
                    stripe_info.price_amount_cents = price_data["amount_cents"]
                    stripe_info.price_currency = price_data["currency"]
                    
                    # Check if price meets minimum amount requirement ($0.50 USD = 50 cents)
                    if price_data["currency"].upper() == "USD" and price_data["amount_cents"] < 50:
                        stripe_info.price_available = False
                        stripe_info.price_status = "below_minimum"
                    else:
                        stripe_info.price_available = True
                        stripe_info.price_status = "available"
                else:
                    stripe_info.price_status = "not_set"
            except Exception as e:
                # Log error but don't fail the response
                print(f"Error fetching price for checklist {checklist.id}: {e}")
                stripe_info.price_available = False
                stripe_info.price_status = "error"
        else:
            stripe_info.price_status = "not_set"
    else:
        stripe_info.price_status = "not_set"
    
    # Build checklist type info
    from app.schemas.checklist import ChecklistTypeInfo
    checklist_type_info = ChecklistTypeInfo(
        id=checklist_type.id,
        code=checklist_type.code,
        name=checklist_type.name,
        description=checklist_type.description,
    )
    
    return AdminChecklistResponse(
        id=checklist.id,
        title=title,
        checklist_type=checklist_type_info,
        law_decree=decree,
        version=_format_version(checklist.version),
        status=checklist.status,
        created_at=checklist.created_at,
        updated_at=checklist.updated_at,
        stripe_info=stripe_info,
    )


def _severity_to_points(severity: SeverityLevel) -> int:
    if severity == SeverityLevel.high:
        return 4
    if severity == SeverityLevel.medium:
        return 3
    return 1


def _points_to_severity(points: int) -> SeverityLevel:
    if points >= 4:
        return SeverityLevel.high
    if points >= 3:
        return SeverityLevel.medium
    return SeverityLevel.low


def _question_points(question: ChecklistQuestion) -> int:
    return getattr(question, "points", None) or _severity_to_points(question.severity or SeverityLevel.low)


def _answer_option_response(option: ChecklistQuestionAnswerOption) -> dict:
    return {
        "position": option.position,
        "label": option.label,
        "score": option.score,
        "choice_code": option.choice_code,
        "description": option.description,
        "illustrative_image_id": option.illustrative_image_id,
    }


def _latest_section_translation(db: Session, section_id: uuid.UUID) -> ChecklistSectionTranslation | None:
    return db.scalar(
        select(ChecklistSectionTranslation)
        .where(ChecklistSectionTranslation.section_id == section_id)
        .order_by(ChecklistSectionTranslation.created_at.desc())
        .limit(1)
    )


def _to_section_response(section: ChecklistSection) -> AdminSectionResponse:
    translation = getattr(section, "_translation", None)
    title = translation.title if translation else section.section_code
    return AdminSectionResponse(id=section.id, checklist_id=section.checklist_id, title=title, order=section.display_order, source_ref=section.source_ref)


def _default_language(db: Session) -> Language | None:
    return db.scalar(select(Language).where(Language.is_default.is_(True)).limit(1)) or db.scalar(select(Language).limit(1))


def _latest_question_translation(db: Session, question_id: uuid.UUID) -> ChecklistQuestionTranslation | None:
    return db.scalar(
        select(ChecklistQuestionTranslation)
        .where(ChecklistQuestionTranslation.question_id == question_id)
        .order_by(ChecklistQuestionTranslation.created_at.desc())
        .limit(1)
    )


def _validate_parent_question(
    db: Session,
    *,
    checklist_id: uuid.UUID,
    section_id: uuid.UUID,
    parent_question_id: uuid.UUID,
) -> None:
    parent_question = db.scalar(
        select(ChecklistQuestion.id).where(
            ChecklistQuestion.id == parent_question_id,
            ChecklistQuestion.checklist_id == checklist_id,
            ChecklistQuestion.section_id == section_id,
        )
    )
    if parent_question is None:
        raise ValueError("parent_question_not_found")


def _to_question_response(question: ChecklistQuestion) -> AdminQuestionResponse:
    translation = getattr(question, "_translation", None)
    legal_requirement = translation.question_text if translation else ""
    explanation = translation.explanation if translation and translation.explanation else ""
    expected_implementation = translation.expected_implementation if translation and translation.expected_implementation else ""
    how_it_works = translation.how_it_works if translation and translation.how_it_works else ""
    severity = question.severity or SeverityLevel.low
    return AdminQuestionResponse(
        id=question.id,
        checklist_id=question.checklist_id,
        section_id=question.section_id,
        parent_question_id=question.parent_question_id,
        question_id=question.question_code,
        question_title=question.question_code,  # Set title to question_id
        security_level=severity,
        audit_type=question.audit_type or "compliance",
        points=_question_points(question),
        answer_logic=question.answer_logic or DEFAULT_ANSWER_LOGIC,
        legal_requirement_title=translation.legal_requirement_title if translation else "",
        legal_requirement_description=translation.legal_requirement_description if translation else "",
        explanation=explanation,
        expected_implementation=expected_implementation,
        how_it_works=how_it_works,
        guidance_score_4=translation.guidance_score_4 if translation else None,
        guidance_score_3=translation.guidance_score_3 if translation else None,
        guidance_score_2=translation.guidance_score_2 if translation else None,
        guidance_score_1=translation.guidance_score_1 if translation else None,
        recommendation_template=translation.recommendation_template if translation else None,
        illustrative_image_id=question.illustrative_image_id,
        note_enabled=question.note_enabled,
        evidence_enabled=question.evidence_enabled,
        answer_options=[_answer_option_response(option) for option in sorted(getattr(question, 'answer_options', []), key=lambda o: o.position)],
        note=question.note_for_user,
        evidence_rule=EvidenceRuleResponse(
            allowed_mime_types=DEFAULT_ALLOWED_MIME_TYPES,
            max_file_size_bytes=DEFAULT_MAX_FILE_SIZE_BYTES,
        ),
    )


def list_checklists(
    db: Session,
    *,
    lang_code: str = "en",
    skip: int = 0,
    limit: int = 50,
    sort_by: str | None = None,
    sort_order: str = "asc",
    search: str | None = None,
) -> tuple[int, list[AdminChecklistResponse]]:
    query = select(Checklist)
    count_query = select(func.count(Checklist.id))

    if search:
        search_term = f"%{search}%"
        query = query.outerjoin(ChecklistTranslation).where(
            or_(
                ChecklistTranslation.title.ilike(search_term),
                ChecklistTranslation.description.ilike(search_term),
            )
        )
        count_query = count_query.select_from(Checklist).outerjoin(ChecklistTranslation).where(
            or_(
                ChecklistTranslation.title.ilike(search_term),
                ChecklistTranslation.description.ilike(search_term),
            )
        )

    sort_column = Checklist.created_at
    if sort_by == "updated_at":
        sort_column = Checklist.updated_at
    elif sort_by == "version":
        sort_column = Checklist.version
    elif sort_by == "status":
        sort_column = Checklist.status

    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    total = db.scalar(count_query) or 0
    rows = db.scalars(query.offset(skip).limit(limit)).all()
    return total, [_to_checklist_response(row, db) for row in rows]
  
def _to_question_response_nested(question: ChecklistQuestion, db: Session) -> AdminQuestionResponse:
    translation = getattr(question, "_translation", None)
    legal_requirement = translation.question_text if translation else ""
    explanation = translation.explanation if translation and translation.explanation else ""
    expected_implementation = translation.expected_implementation if translation and translation.expected_implementation else ""
    how_it_works = translation.how_it_works if translation and translation.how_it_works else ""
    severity = question.severity or SeverityLevel.low
    # Recursively fetch sub-questions
    sub_questions = []
    for subq in sorted(question.sub_questions, key=lambda q: q.display_order):
        subq._translation = _latest_question_translation(db, subq.id)
        sub_questions.append(_to_question_response_nested(subq, db))
    return AdminQuestionResponse(
        id=question.id,
        checklist_id=question.checklist_id,
        section_id=question.section_id,
        parent_question_id=question.parent_question_id,
        question_id=question.question_code,
        question_title=question.question_code,  # Set title to question_id
        security_level=severity,
        points=_question_points(question),
        answer_logic=question.answer_logic or DEFAULT_ANSWER_LOGIC,
        audit_type=question.audit_type or "compliance",
        legal_requirement_title=translation.legal_requirement_title if translation else "",
        legal_requirement_description=translation.legal_requirement_description if translation else "",
        explanation=explanation,
        expected_implementation=expected_implementation,
        how_it_works=how_it_works,
        guidance_score_4=translation.guidance_score_4 if translation else None,
        guidance_score_3=translation.guidance_score_3 if translation else None,
        guidance_score_2=translation.guidance_score_2 if translation else None,
        guidance_score_1=translation.guidance_score_1 if translation else None,
        recommendation_template=translation.recommendation_template if translation else None,
        illustrative_image_id=question.illustrative_image_id,
        note_enabled=question.note_enabled,
        evidence_enabled=question.evidence_enabled,
        answer_options=[_answer_option_response(option) for option in sorted(getattr(question, 'answer_options', []), key=lambda o: o.position)],
        note=question.note_for_user,
        evidence_rule=EvidenceRuleResponse(
            allowed_mime_types=DEFAULT_ALLOWED_MIME_TYPES,
            max_file_size_bytes=DEFAULT_MAX_FILE_SIZE_BYTES,
        ),
        sub_questions=sub_questions,
    )




def get_checklist(db: Session, *, checklist_id, lang_code: str = "en") -> AdminChecklistResponse | None:
    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        return None
    return _to_checklist_response(checklist, db)


def create_checklist(db: Session, *, actor: User, payload: AdminChecklistCreateRequest, lang_code: str = "en") -> AdminChecklistResponse:
    # Create unique checklist type for each checklist to prevent duplicates
    checklist_type = _get_or_create_unique_checklist_type(db, payload.title, payload.law_decree)

    checklist = Checklist(
        checklist_type_id=checklist_type.id,
        version="1.0",  # Always start with version 1.0
        status=payload.status,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.add(checklist)
    db.flush()
    language = _default_language(db)
    if language is not None:
        db.add(
            ChecklistTranslation(
                checklist_id=checklist.id,
                language_id=language.id,
                title=payload.title,
                description=payload.law_decree,
            )
        )
    db.commit()
    db.refresh(checklist)
    
    # Create Stripe product for the checklist
    try:
        create_stripe_product_for_checklist(
            db,
            checklist_id=checklist.id,
            title=payload.title,
            description=payload.law_decree
        )
    except Exception as e:
        # Log error but don't fail checklist creation
        print(f"Error creating Stripe product for checklist {checklist.id}: {e}")
    
    # Add audit logging
    try:
        AuditLogger.log_checklist_action(
            db=db,
            actor_user_id=actor.id,
            action="checklist_created",
            target_id=checklist.id,
            before_json=None,
            after_json={
                "title": payload.title,
                "status": payload.status.value if hasattr(payload.status, 'value') else str(payload.status),
                "law_decree": payload.law_decree
            },
            changes_summary=f"Created checklist: {payload.title}"
        )
    except Exception as e:
        # Log error but don't fail checklist creation
        print(f"Error creating audit log for checklist {checklist.id}: {e}")
    
    return _to_checklist_response(checklist, db)


def update_checklist(db: Session, *, actor: User, checklist_id, payload: AdminChecklistUpdateRequest, lang_code: str = "en") -> AdminChecklistResponse | None:
    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        return None

    # Update translation for title and description (law_decree)
    language = _default_language(db)
    translation = None
    if language is not None:
        translation = db.scalar(
            select(ChecklistTranslation)
            .where(ChecklistTranslation.checklist_id == checklist_id)
            .where(ChecklistTranslation.language_id == language.id)
        )
        if translation is None:
            translation = ChecklistTranslation(
                checklist_id=checklist_id,
                language_id=language.id,
                title=payload.title or f"Checklist v{checklist.version}",
                description=payload.law_decree or None,
            )
            db.add(translation)
        else:
            if payload.title is not None:
                translation.title = payload.title
            if payload.law_decree is not None:
                translation.description = payload.law_decree

    # Check if any fields are actually being updated
    fields_updated = False
    
    if payload.title is not None:
        fields_updated = True
    if payload.law_decree is not None:
        fields_updated = True
    if payload.status is not None:
        checklist.status = payload.status
        fields_updated = True
    
    # Auto-increment version if any fields were updated
    if fields_updated:
        checklist.increment_version()
    
    checklist.updated_by = actor.id

    db.commit()
    db.refresh(checklist)
    return _to_checklist_response(checklist, db)


def publish_checklist(db: Session, *, actor: User, checklist_id, payload: PublishChecklistRequest, lang_code: str = "en") -> AdminChecklistResponse | None:
    return update_checklist(
        db,
        actor=actor,
        checklist_id=checklist_id,
        payload=AdminChecklistUpdateRequest(status=payload.status),
        lang_code=lang_code,
    )


def delete_checklist(db: Session, *, checklist_id) -> bool:
    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        return False
    
    # Check if checklist has any assessments (RESTRICT constraint)
    assessment_count = db.scalar(
        select(func.count(Assessment.id)).where(Assessment.checklist_id == checklist_id)
    )
    if assessment_count > 0:
        raise ValueError(f"Cannot delete checklist with {assessment_count} associated assessments. Delete assessments first.")
    
    # Check if checklist has any payments (RESTRICT constraint)
    from app.models.payment import Payment
    payment_count = db.scalar(
        select(func.count(Payment.id)).where(Payment.checklist_id == checklist_id)
    )
    if payment_count > 0:
        raise ValueError(f"Cannot delete checklist with {payment_count} associated payments. Delete payments first.")
    
    # Delete Stripe product if no prices exist
    try:
        from app.services.stripe_products import delete_stripe_product_for_checklist
        stripe_deleted = delete_stripe_product_for_checklist(db, checklist_id=checklist_id)
        if not stripe_deleted:
            print(f"Warning: Could not delete Stripe product for checklist {checklist_id} - prices still exist")
    except Exception as e:
        print(f"Error deleting Stripe product for checklist {checklist_id}: {e}")
        # Continue with checklist deletion even if Stripe deletion fails
    
    # Delete the checklist (CASCADE will handle sections, questions, and translations)
    db.delete(checklist)
    db.commit()
    return True


def list_sections(
    db: Session,
    *,
    checklist_id,
    lang_code: str = "en",
    skip: int = 0,
    limit: int = 50,
    sort_by: str | None = None,
    sort_order: str = "asc",
    search: str | None = None,
) -> tuple[int, list[AdminSectionResponse]]:
    query = select(ChecklistSection).where(ChecklistSection.checklist_id == checklist_id)
    count_query = select(func.count(ChecklistSection.id)).where(ChecklistSection.checklist_id == checklist_id)

    if search:
        search_term = f"%{search}%"
        query = query.outerjoin(ChecklistSectionTranslation).where(
            ChecklistSection.checklist_id == checklist_id,
            or_(ChecklistSectionTranslation.title.ilike(search_term), ChecklistSection.section_code.ilike(search_term)),
        )
        count_query = select(func.count(ChecklistSection.id)).outerjoin(ChecklistSectionTranslation).where(
            ChecklistSection.checklist_id == checklist_id,
            or_(ChecklistSectionTranslation.title.ilike(search_term), ChecklistSection.section_code.ilike(search_term)),
        )

    sort_column = ChecklistSection.display_order
    if sort_by == "title":
        sort_column = ChecklistSection.display_order
    elif sort_by == "section_code":
        sort_column = ChecklistSection.section_code

    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    total = db.scalar(count_query) or 0
    rows = db.scalars(query.offset(skip).limit(limit)).all()
    for row in rows:
        row._translation = _latest_section_translation(db, row.id)
    return total, [_to_section_response(row) for row in rows]


def create_section(db: Session, *, checklist_id, payload: AdminSectionCreateRequest, lang_code: str = "en") -> AdminSectionResponse:
    section = ChecklistSection(
        checklist_id=checklist_id,
        section_code=f"SEC-{payload.order}",
        source_ref=payload.source_ref,
        display_order=payload.order,
    )
    db.add(section)
    db.flush()
    language = _default_language(db)
    if language is not None:
        db.add(
            ChecklistSectionTranslation(
                section_id=section.id,
                language_id=language.id,
                title=payload.title,
            )
        )
    db.commit()
    db.refresh(section)
    # Load the translation for the response
    section._translation = _latest_section_translation(db, section.id)
    return _to_section_response(section)


def update_section(db: Session, *, checklist_id, section_id, payload: AdminSectionUpdateRequest, lang_code: str = "en") -> AdminSectionResponse | None:
    section = db.scalar(
        select(ChecklistSection).where(ChecklistSection.id == section_id, ChecklistSection.checklist_id == checklist_id)
    )
    if section is None:
        return None

    if payload.title is not None:
        # Update translation for title
        language = _default_language(db)
        if language is not None:
            translation = db.scalar(
                select(ChecklistSectionTranslation)
                .where(ChecklistSectionTranslation.section_id == section_id)
                .where(ChecklistSectionTranslation.language_id == language.id)
            )
            if translation is None:
                translation = ChecklistSectionTranslation(
                    section_id=section_id,
                    language_id=language.id,
                    title=payload.title,
                )
                db.add(translation)
            else:
                translation.title = payload.title
    
    # Check if any fields are actually being updated
    fields_updated = False
    
    if payload.title is not None:
        fields_updated = True
    if payload.order is not None:
        section.display_order = payload.order
        fields_updated = True
    
    # Auto-increment checklist version if any fields were updated
    if fields_updated:
        checklist = db.get(Checklist, checklist_id)
        if checklist:
            checklist.increment_version()

    db.commit()
    db.refresh(section)
    section._translation = _latest_section_translation(db, section.id)
    return _to_section_response(section)


def delete_section(db: Session, *, checklist_id, section_id) -> bool:
    section = db.scalar(
        select(ChecklistSection).where(ChecklistSection.id == section_id, ChecklistSection.checklist_id == checklist_id)
    )
    if section is None:
        return False
    db.delete(section)
    db.commit()
    return True

def list_questions(
    db: Session,
    *,
    checklist_id,
    section_id,
    lang_code: str = "en",
    skip: int = 0,
    limit: int = 50,
    sort_by: str | None = None,
    sort_order: str = "asc",
    search: str | None = None,
) -> tuple[int, list[AdminQuestionResponse]]:
    query = select(ChecklistQuestion).where(
        ChecklistQuestion.checklist_id == checklist_id,
        ChecklistQuestion.section_id == section_id,
    )
    count_query = select(func.count(ChecklistQuestion.id)).where(
        ChecklistQuestion.checklist_id == checklist_id,
        ChecklistQuestion.section_id == section_id,
    )

    if search:
        search_term = f"%{search}%"
        query = query.outerjoin(ChecklistQuestionTranslation).where(
            ChecklistQuestion.checklist_id == checklist_id,
            ChecklistQuestion.section_id == section_id,
            or_(
                ChecklistQuestionTranslation.question_text.ilike(search_term),
                ChecklistQuestionTranslation.explanation.ilike(search_term),
                ChecklistQuestionTranslation.expected_implementation.ilike(search_term),
                ChecklistQuestion.question_code.ilike(search_term),
            ),
        )
        count_query = select(func.count(ChecklistQuestion.id)).outerjoin(ChecklistQuestionTranslation).where(
            ChecklistQuestion.checklist_id == checklist_id,
            ChecklistQuestion.section_id == section_id,
            or_(
                ChecklistQuestionTranslation.question_text.ilike(search_term),
                ChecklistQuestionTranslation.explanation.ilike(search_term),
                ChecklistQuestionTranslation.expected_implementation.ilike(search_term),
                ChecklistQuestion.question_code.ilike(search_term),
            ),
        )

    sort_column = ChecklistQuestion.display_order
    if sort_by == "question_id":
        sort_column = ChecklistQuestion.question_code
    elif sort_by == "severity":
        sort_column = ChecklistQuestion.severity

    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    total = db.scalar(count_query) or 0
    rows = db.scalars(query.offset(skip).limit(limit)).all()
    for row in rows:
        row._translation = _latest_question_translation(db, row.id)
    return total, [_to_question_response(row) for row in rows]
  
def reorder_sections(db: Session, *, checklist_id, section_orders: list[dict]) -> list[AdminSectionResponse]:
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"SERVICE REORDER - Starting reordering for checklist {checklist_id}")
    
    # Convert SectionOrderItem objects to dicts if needed
    if section_orders and hasattr(section_orders[0], 'section_id'):
        logger.info("SERVICE REORDER - Converting SectionOrderItem objects to dicts")
        section_orders = [{"section_id": item.section_id, "order": item.order} for item in section_orders]
    
    logger.info(f"SERVICE REORDER - Processing {len(section_orders)} section orders")
    
    # Validate all sections exist and belong to the checklist
    section_ids = [item["section_id"] for item in section_orders]
    sections = db.scalars(
        select(ChecklistSection).where(
            ChecklistSection.id.in_(section_ids),
            ChecklistSection.checklist_id == checklist_id
        )
    ).all()
    
    if len(sections) != len(section_ids):
        raise ValueError("One or more sections not found")
    
    # Create a mapping of section_id to section object
    section_map = {section.id: section for section in sections}
    
    # Validate orders are unique and positive
    orders = [item["order"] for item in section_orders]
    if len(set(orders)) != len(orders):
        raise ValueError("Orders must be unique")
    if any(order < 1 for order in orders):
        raise ValueError("Orders must be positive")
    
    # Check for existing orders that would conflict
    existing_sections = db.scalars(
        select(ChecklistSection)
        .where(
            ChecklistSection.checklist_id == checklist_id,
            ChecklistSection.display_order.in_(orders),
            ~ChecklistSection.id.in_(section_ids)  # Exclude sections we're updating
        )
    ).all()
    
    if existing_sections:
        conflicts = []
        for section in existing_sections:
            conflicts.append(f"Order {section.display_order} is already assigned to section '{section.section_code}'")
        raise ValueError("; ".join(conflicts))
    
    # Update the display order for each section using temporary values to avoid constraint violations
    # Step 1: Assign temporary negative orders to avoid conflicts using bulk update
    temp_order = -1
    temp_updates = []
    for item in section_orders:
        temp_updates.append({
            "id": item["section_id"],
            "display_order": temp_order
        })
        temp_order -= 1
    
    # Bulk update with temporary orders
    if temp_updates:
        db.execute(
            update(ChecklistSection)
            .where(ChecklistSection.id.in_([item["id"] for item in temp_updates]))
            .values(display_order=case(
                *((
                    ChecklistSection.id == item["id"], 
                    item["display_order"]
                ) for item in temp_updates)
            ))
        )
    
    db.flush()  # Apply temporary orders
    
    # Step 2: Now assign the final orders using bulk update
    final_updates = []
    for item in section_orders:
        final_updates.append({
            "id": item["section_id"],
            "display_order": item["order"]
        })
    
    # Bulk update with final orders
    if final_updates:
        db.execute(
            update(ChecklistSection)
            .where(ChecklistSection.id.in_([item["id"] for item in final_updates]))
            .values(display_order=case(
                *((
                    ChecklistSection.id == item["id"], 
                    item["display_order"]
                ) for item in final_updates)
            ))
        )
    
    # Auto-increment checklist version since sections were reordered
    checklist = db.get(Checklist, checklist_id)
    if checklist:
        checklist.increment_version()
    
    db.commit()
    
    # Return updated sections in order
    updated_sections = db.scalars(
        select(ChecklistSection).where(ChecklistSection.checklist_id == checklist_id).order_by(asc(ChecklistSection.display_order))
    ).all()
    
    for section in updated_sections:
        section._translation = _latest_section_translation(db, section.id)
    
    return [_to_section_response(section) for section in updated_sections]


def reorder_questions(db: Session, *, checklist_id, section_id, question_orders: list[dict]) -> list[AdminQuestionResponse]:
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"QUESTION REORDER - Starting reordering for checklist {checklist_id}, section {section_id}")
    
    # Convert QuestionOrderItem objects to dicts if needed
    if question_orders and hasattr(question_orders[0], 'question_id'):
        logger.info("QUESTION REORDER - Converting QuestionOrderItem objects to dicts")
        question_orders = [{"question_id": item.question_id, "order": item.order} for item in question_orders]
    
    logger.info(f"QUESTION REORDER - Processing {len(question_orders)} question orders")
    
    # Validate all questions exist and belong to checklist/section
    question_ids = [item["question_id"] for item in question_orders]
    questions = db.scalars(
        select(ChecklistQuestion).where(
            ChecklistQuestion.id.in_(question_ids),
            ChecklistQuestion.checklist_id == checklist_id,
            ChecklistQuestion.section_id == section_id
        )
    ).all()
    
    if len(questions) != len(question_ids):
        raise ValueError("One or more questions not found")
    
    # Create a mapping of question_id to question object
    question_map = {question.id: question for question in questions}
    
    # Validate orders are unique and positive
    orders = [item["order"] for item in question_orders]
    if len(set(orders)) != len(orders):
        raise ValueError("Orders must be unique")
    if any(order < 1 for order in orders):
        raise ValueError("Orders must be positive")
    
    # Check for existing orders that would conflict
    existing_questions = db.scalars(
        select(ChecklistQuestion)
        .where(
            ChecklistQuestion.section_id == section_id,
            ChecklistQuestion.display_order.in_(orders),
            ~ChecklistQuestion.id.in_(question_ids)  # Exclude questions we're updating
        )
    ).all()
    
    if existing_questions:
        conflicts = []
        for question in existing_questions:
            conflicts.append(f"Order {question.display_order} is already assigned to question '{question.question_code}'")
        raise ValueError("; ".join(conflicts))
    
    # Build parent-child relationships for validation
    parent_child_map = {}
    for question in questions:
        if question.parent_question_id:
            if question.parent_question_id not in parent_child_map:
                parent_child_map[question.parent_question_id] = []
            parent_child_map[question.parent_question_id].append(question.id)
    
    # Validate parent-child ordering constraints
    for item in question_orders:
        question_id = item["question_id"]
        new_order = item["order"]
        question = question_map[question_id]
        
        # Check if this question has children
        if question_id in parent_child_map:
            child_ids = parent_child_map[question_id]
            
            # Ensure all children have higher order numbers than parent
            for child_id in child_ids:
                child_order = next((q["order"] for q in question_orders if q["question_id"] == child_id), None)
                if child_order is not None and child_order <= new_order:
                    raise ValueError(f"Child question cannot be ordered above its parent question (parent order: {new_order}, child order: {child_order})")
    
    # Update display order for each question using temporary values to avoid constraint violations
    # Step 1: Assign temporary negative orders to avoid conflicts using bulk update
    temp_order = -1
    temp_updates = []
    for item in question_orders:
        temp_updates.append({
            "id": item["question_id"],
            "display_order": temp_order
        })
        temp_order -= 1
    
    # Bulk update with temporary orders
    if temp_updates:
        db.execute(
            update(ChecklistQuestion)
            .where(ChecklistQuestion.id.in_([item["id"] for item in temp_updates]))
            .values(display_order=case(
                *((
                    ChecklistQuestion.id == item["id"], 
                    item["display_order"]
                ) for item in temp_updates)
            ))
        )
    
    db.flush()  # Apply temporary orders
    
    # Step 2: Now assign final orders using bulk update
    final_updates = []
    for item in question_orders:
        final_updates.append({
            "id": item["question_id"],
            "display_order": item["order"]
        })
    
    # Bulk update with final orders
    if final_updates:
        db.execute(
            update(ChecklistQuestion)
            .where(ChecklistQuestion.id.in_([item["id"] for item in final_updates]))
            .values(display_order=case(
                *((
                    ChecklistQuestion.id == item["id"], 
                    item["display_order"]
                ) for item in final_updates)
            ))
        )
    
    # Auto-increment checklist version since questions were reordered
    checklist = db.get(Checklist, checklist_id)
    if checklist:
        checklist.increment_version()
    
    db.commit()
    
    # Return updated questions in order
    updated_questions = db.scalars(
        select(ChecklistQuestion)
        .where(ChecklistQuestion.checklist_id == checklist_id, ChecklistQuestion.section_id == section_id)
        .order_by(asc(ChecklistQuestion.display_order))
    ).all()
    
    for question in updated_questions:
        question._translation = _latest_question_translation(db, question.id)
    
    return [_to_question_response(question) for question in updated_questions]




def get_question(db: Session, *, checklist_id, section_id, question_id, lang_code: str = "en") -> AdminQuestionResponse | None:
    question = db.scalar(
        select(ChecklistQuestion).where(
            ChecklistQuestion.id == question_id,
            ChecklistQuestion.checklist_id == checklist_id,
            ChecklistQuestion.section_id == section_id,
        )
    )
    if question is None:
        return None
    question._translation = _latest_question_translation(db, question.id)
    return _to_question_response(question)

def create_question(db: Session, *, checklist_id, section_id, payload: AdminQuestionCreateRequest, lang_code: str = "en") -> AdminQuestionResponse:
    # Check if question_code already exists in this checklist
    existing_question = db.scalar(
        select(ChecklistQuestion)
        .where(
            ChecklistQuestion.checklist_id == checklist_id,
            ChecklistQuestion.question_code == payload.question_id
        )
    )
    if existing_question:
        if payload.parent_question_id:
            raise ValueError(f"Question code '{payload.question_id}' already exists in this checklist. Child questions must have unique identifiers (e.g., '{payload.question_id}_1', '{payload.question_id}_2').")
        else:
            raise ValueError(f"Question code '{payload.question_id}' already exists in this checklist")
    
    last_order = db.scalar(
        select(ChecklistQuestion.display_order)
        .where(ChecklistQuestion.section_id == section_id)
        .order_by(ChecklistQuestion.display_order.desc())
        .limit(1)
    )
    next_order = (last_order or 0) + 1

    if payload.parent_question_id is not None:
        _validate_parent_question(
            db,
            checklist_id=checklist_id,
            section_id=section_id,
            parent_question_id=payload.parent_question_id,
        )

    question = ChecklistQuestion(
        checklist_id=checklist_id,
        section_id=section_id,
        parent_question_id=payload.parent_question_id,
        question_code=payload.question_id,
        audit_type=payload.audit_type,
        severity=payload.security_level,
        points=payload.points if payload.points is not None else _severity_to_points(payload.security_level),
        answer_logic=payload.answer_logic,
        report_domain=None,
        report_chapter=None,
        illustrative_image_id=payload.illustrative_image_id,
        note_for_user=payload.note,
        note_enabled=payload.note_enabled,
        evidence_enabled=payload.evidence_enabled,
        display_order=next_order,
        is_active=True,
    )
    db.add(question)
    db.flush()

    language = _default_language(db)
    if language is not None:
        db.add(
            ChecklistQuestionTranslation(
                question_id=question.id,
                language_id=language.id,
                paragraph_title=None,  # Removed question_title
                question_text=payload.legal_requirement_title or "",
                legal_requirement_title=payload.legal_requirement_title or "",
                legal_requirement_description=payload.legal_requirement_description or "",
                explanation=payload.explanation,
                expected_implementation=payload.expected_implementation,
                how_it_works=payload.how_it_works,
                guidance_score_4=payload.guidance_score_4,
                guidance_score_3=payload.guidance_score_3,
                guidance_score_2=payload.guidance_score_2,
                guidance_score_1=payload.guidance_score_1,
                recommendation_template=payload.recommendation_template,
            )
        )

    if payload.answer_options is not None:
        for option in payload.answer_options:
            db.add(
                ChecklistQuestionAnswerOption(
                    question_id=question.id,
                    position=option.position,
                    choice_code=option.choice_code,
                    label=option.label,
                    score=option.score,
                    description=option.description,
                    illustrative_image_id=option.illustrative_image_id,
                )
            )
    db.commit()
    db.refresh(question)
    question._translation = _latest_question_translation(db, question.id)
    return _to_question_response(question)


def update_question(
    db: Session,
    *,
    checklist_id,
    section_id,
    question_id,
    payload: AdminQuestionUpdateRequest,
    lang_code: str = "en",
) -> AdminQuestionResponse | None:
    question = db.scalar(
        select(ChecklistQuestion).where(
            ChecklistQuestion.id == question_id,
            ChecklistQuestion.checklist_id == checklist_id,
            ChecklistQuestion.section_id == section_id,
        )
    )
    if question is None:
        return None

    if payload.question_id is not None:
        question.question_code = payload.question_id
    if payload.audit_type is not None:
        question.audit_type = payload.audit_type
    if "parent_question_id" in payload.model_fields_set:
        if payload.parent_question_id == question.id:
            raise ValueError("parent_question_invalid")
        if payload.parent_question_id is not None:
            _validate_parent_question(
                db,
                checklist_id=checklist_id,
                section_id=section_id,
                parent_question_id=payload.parent_question_id,
            )
        question.parent_question_id = payload.parent_question_id
    if payload.security_level is not None:
        question.severity = payload.security_level
        if payload.points is None:
            question.points = _severity_to_points(payload.security_level)
    if payload.points is not None:
        question.points = payload.points
    if payload.answer_logic is not None:
        question.answer_logic = payload.answer_logic
    if "note" in payload.model_fields_set:
        question.note_for_user = payload.note
    if "illustrative_image_id" in payload.model_fields_set:
        question.illustrative_image_id = payload.illustrative_image_id
    if "note_enabled" in payload.model_fields_set:
        question.note_enabled = payload.note_enabled
    if "evidence_enabled" in payload.model_fields_set:
        question.evidence_enabled = payload.evidence_enabled
    if payload.order is not None:
        question.display_order = payload.order
    if payload.answer_options is not None:
        # Use direct DELETE to ensure existing options are removed immediately
        db.execute(
            delete(ChecklistQuestionAnswerOption).where(ChecklistQuestionAnswerOption.question_id == question.id)
        )
        
        # Now add the new options
        for option in payload.answer_options:
            db.add(
                ChecklistQuestionAnswerOption(
                    question_id=question.id,
                    position=option.position,
                    choice_code=option.choice_code,
                    label=option.label,
                    score=option.score,
                    description=option.description,
                    illustrative_image_id=option.illustrative_image_id,
                )
            )

    translation = _latest_question_translation(db, question.id)
    if translation is None:
        language = _default_language(db)
        if language is not None:
            translation = ChecklistQuestionTranslation(
                question_id=question.id,
                language_id=language.id,
                paragraph_title=None,  # Removed question_title
                question_text=payload.legal_requirement_title or "",
                legal_requirement_title=payload.legal_requirement_title or "",
                legal_requirement_description=payload.legal_requirement_description or "",
                explanation=payload.explanation,
                expected_implementation=payload.expected_implementation,
                how_it_works=payload.how_it_works,
                guidance_score_4=payload.guidance_score_4,
                guidance_score_3=payload.guidance_score_3,
                guidance_score_2=payload.guidance_score_2,
                guidance_score_1=payload.guidance_score_1,
                recommendation_template=payload.recommendation_template,
            )
            db.add(translation)
    else:
        # Removed question_title update
        pass
        if payload.legal_requirement_title is not None:
            translation.question_text = payload.legal_requirement_title
            translation.legal_requirement_title = payload.legal_requirement_title
        if payload.legal_requirement_description is not None:
            translation.legal_requirement_description = payload.legal_requirement_description
        if payload.explanation is not None:
            translation.explanation = payload.explanation
        if payload.expected_implementation is not None:
            translation.expected_implementation = payload.expected_implementation
        if payload.how_it_works is not None:
            translation.how_it_works = payload.how_it_works
        if payload.guidance_score_4 is not None:
            translation.guidance_score_4 = payload.guidance_score_4
        if payload.guidance_score_3 is not None:
            translation.guidance_score_3 = payload.guidance_score_3
        if payload.guidance_score_2 is not None:
            translation.guidance_score_2 = payload.guidance_score_2
        if payload.guidance_score_1 is not None:
            translation.guidance_score_1 = payload.guidance_score_1
        if payload.recommendation_template is not None:
            translation.recommendation_template = payload.recommendation_template

    # Auto-increment checklist version since question was modified
    checklist = db.get(Checklist, checklist_id)
    if checklist:
        checklist.increment_version()

    db.commit()
    db.refresh(question)
    question._translation = _latest_question_translation(db, question.id)
    return _to_question_response(question)


def delete_question(db: Session, *, checklist_id, section_id, question_id) -> bool:
    question = db.scalar(
        select(ChecklistQuestion).where(
            ChecklistQuestion.id == question_id,
            ChecklistQuestion.checklist_id == checklist_id,
            ChecklistQuestion.section_id == section_id,
        )
    )
    if question is None:
        return False
    db.delete(question)
    db.commit()
    return True
