from __future__ import annotations

import uuid

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.checklist import (
    Checklist,
    ChecklistQuestion,
    ChecklistQuestionTranslation,
    ChecklistSection,
    ChecklistSectionTranslation,
    ChecklistStatus,
    ChecklistTranslation,
    ChecklistType,
    SeverityLevel,
)
from app.models.reference import Language
from app.models.user import User
from app.schemas.admin_checklist import (
    AdminChecklistCreateRequest,
    AdminChecklistResponse,
    AdminChecklistUpdateRequest,
    AdminQuestionCreateRequest,
    AdminQuestionUpdateRequest,
    AdminQuestionResponse,
    AdminSectionCreateRequest,
    AdminSectionUpdateRequest,
    AdminSectionResponse,
    EvidenceRuleResponse,
    PublishChecklistRequest,
)

DEFAULT_ALLOWED_MIME_TYPES = ["application/pdf", "image/png", "image/jpeg"]
DEFAULT_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


def _ensure_default_checklist_type(db: Session) -> ChecklistType:
    checklist_type = db.scalar(select(ChecklistType).where(ChecklistType.code == "compliance"))
    if checklist_type is None:
        checklist_type = ChecklistType(code="compliance", name="Compliance", description="Default compliance type", is_active=True)
        db.add(checklist_type)
        db.flush()
    return checklist_type


def _format_version(version: int) -> str:
    return f"v{version}.0"


def _to_checklist_response(checklist: Checklist) -> AdminChecklistResponse:
    # Get translation for title/description
    translation = None
    if hasattr(checklist, 'translations'):
        # If relationship is loaded
        translation = next(iter(checklist.translations), None)
    else:
        # Fallback: query translation
        from app.models.checklist import ChecklistTranslation
        from app.db.session import SessionLocal
        db = SessionLocal()
        translation = db.query(ChecklistTranslation).filter_by(checklist_id=checklist.id).first()
        db.close()

    title = translation.title if translation else f"Checklist v{checklist.version}"
    # Get ChecklistType for description
    checklist_type = getattr(checklist, "checklist_type", None)
    if not checklist_type:
        from app.models.checklist import ChecklistType
        from app.db.session import SessionLocal
        db = SessionLocal()
        checklist_type = db.query(ChecklistType).filter_by(id=checklist.checklist_type_id).first()
        db.close()
    decree = (translation.description if translation and translation.description else (checklist_type.description if checklist_type else title))
    return AdminChecklistResponse(
        id=checklist.id,
        title=title,
        law_decree=decree,
        version=_format_version(checklist.version),
        status=checklist.status,
        created_at=checklist.created_at,
        updated_at=checklist.updated_at,
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
    return AdminSectionResponse(id=section.id, checklist_id=section.checklist_id, title=title, order=section.display_order)


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
    severity = question.severity or SeverityLevel.low
    return AdminQuestionResponse(
        id=question.id,
        checklist_id=question.checklist_id,
        section_id=question.section_id,
        parent_question_id=question.parent_question_id,
        question_id=question.question_code,
        security_level=severity,
        legal_requirement=legal_requirement,
        explanation=explanation,
        expected_implementation=expected_implementation,
        points=_severity_to_points(severity),
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
    return total, [_to_checklist_response(row) for row in rows]


def get_checklist(db: Session, *, checklist_id) -> AdminChecklistResponse | None:
    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        return None
    return _to_checklist_response(checklist)


def create_checklist(db: Session, *, actor: User, payload: AdminChecklistCreateRequest) -> AdminChecklistResponse:
    # Always create or update ChecklistType with name/description from payload
    checklist_type = db.scalar(select(ChecklistType).where(ChecklistType.code == payload.checklist_type_code))
    if checklist_type is None:
        checklist_type = ChecklistType(
            code=payload.checklist_type_code,
            name=payload.title,
            description=payload.law_decree,
            is_active=True,
        )
        db.add(checklist_type)
        db.flush()
    else:
        checklist_type.name = payload.title
        checklist_type.description = payload.law_decree
        db.flush()

    checklist = Checklist(
        checklist_type_id=checklist_type.id,
        version=payload.version,
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
    return _to_checklist_response(checklist)


def update_checklist(db: Session, *, actor: User, checklist_id, payload: AdminChecklistUpdateRequest) -> AdminChecklistResponse | None:
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

    # Update version if provided
    if payload.version is not None:
        checklist.version = payload.version
    # Update status if provided
    if payload.status is not None:
        checklist.status = payload.status
    checklist.updated_by = actor.id

    db.commit()
    db.refresh(checklist)
    return _to_checklist_response(checklist)


def publish_checklist(db: Session, *, actor: User, checklist_id, payload: PublishChecklistRequest) -> AdminChecklistResponse | None:
    return update_checklist(
        db,
        actor=actor,
        checklist_id=checklist_id,
        payload=AdminChecklistUpdateRequest(status=payload.status),
    )


def delete_checklist(db: Session, *, checklist_id) -> bool:
    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        return False
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


def create_section(db: Session, *, checklist_id, payload: AdminSectionCreateRequest) -> AdminSectionResponse:
    section = ChecklistSection(
        checklist_id=checklist_id,
        section_code=f"SEC-{payload.order}",
        source_ref=None,
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
    return _to_section_response(section)


def update_section(db: Session, *, checklist_id, section_id, payload: AdminSectionUpdateRequest) -> AdminSectionResponse | None:
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
    
    if payload.order is not None:
        section.display_order = payload.order

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


def get_question(db: Session, *, checklist_id, section_id, question_id) -> AdminQuestionResponse | None:
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


def create_question(db: Session, *, checklist_id, section_id, payload: AdminQuestionCreateRequest) -> AdminQuestionResponse:
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
        severity=payload.security_level,
        report_domain=None,
        report_chapter=None,
        illustrative_image_url=None,
        note_for_user=payload.note,
        note_enabled=True,
        evidence_enabled=True,
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
                question_text=payload.legal_requirement,
                explanation=payload.explanation,
                expected_implementation=payload.expected_implementation,
                recommendation_template=None,
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
    if "note" in payload.model_fields_set:
        question.note_for_user = payload.note
    if payload.order is not None:
        question.display_order = payload.order

    translation = _latest_question_translation(db, question.id)
    if translation is None:
        language = _default_language(db)
        if language is not None:
            translation = ChecklistQuestionTranslation(
                question_id=question.id,
                language_id=language.id,
                question_text=payload.legal_requirement or "",
                explanation=payload.explanation,
                expected_implementation=payload.expected_implementation,
                recommendation_template=None,
            )
            db.add(translation)
    elif payload.legal_requirement is not None or payload.explanation is not None or payload.expected_implementation is not None:
        if payload.legal_requirement is not None:
            translation.question_text = payload.legal_requirement
        if payload.explanation is not None:
            translation.explanation = payload.explanation
        if payload.expected_implementation is not None:
            translation.expected_implementation = payload.expected_implementation

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
