from __future__ import annotations

from sqlalchemy import asc, select
from sqlalchemy.orm import Session

from app.models.checklist import (
    Checklist,
    ChecklistQuestion,
    ChecklistSection,
    ChecklistStatus,
    ChecklistType,
    QuestionScoreMode,
    SeverityLevel,
)
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
    return AdminChecklistResponse(
        id=checklist.id,
        title=checklist.title,
        law_decree=checklist.description or checklist.title,
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
    return 2


def _points_to_severity(points: int) -> SeverityLevel:
    if points >= 4:
        return SeverityLevel.high
    if points == 3:
        return SeverityLevel.medium
    return SeverityLevel.low


def _to_section_response(section: ChecklistSection) -> AdminSectionResponse:
    return AdminSectionResponse(id=section.id, checklist_id=section.checklist_id, title=section.title, order=section.display_order)


def _to_question_response(question: ChecklistQuestion) -> AdminQuestionResponse:
    return AdminQuestionResponse(
        id=question.id,
        checklist_id=question.checklist_id,
        section_id=question.section_id,
        question_id=question.question_code,
        security_level=question.severity,
        legal_requirement=question.legal_requirement,
        explanation=question.explanation or "",
        expected_implementation=question.expected_implementation or "",
        points=_severity_to_points(question.severity),
        evidence_rule=EvidenceRuleResponse(
            allowed_mime_types=DEFAULT_ALLOWED_MIME_TYPES,
            max_file_size_bytes=DEFAULT_MAX_FILE_SIZE_BYTES,
        ),
    )


def list_checklists(db: Session) -> list[AdminChecklistResponse]:
    rows = db.scalars(select(Checklist).order_by(asc(Checklist.created_at))).all()
    return [_to_checklist_response(row) for row in rows]


def get_checklist(db: Session, *, checklist_id) -> AdminChecklistResponse | None:
    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        return None
    return _to_checklist_response(checklist)


def create_checklist(db: Session, *, actor: User, payload: AdminChecklistCreateRequest) -> AdminChecklistResponse:
    checklist_type = _ensure_default_checklist_type(db)
    checklist = Checklist(
        checklist_type_id=checklist_type.id,
        version=payload.version,
        title=payload.title,
        description=payload.law_decree,
        status=payload.status,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.add(checklist)
    db.commit()
    db.refresh(checklist)
    return _to_checklist_response(checklist)


def update_checklist(db: Session, *, actor: User, checklist_id, payload: AdminChecklistUpdateRequest) -> AdminChecklistResponse | None:
    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        return None

    if payload.title is not None:
        checklist.title = payload.title
    if payload.law_decree is not None:
        checklist.description = payload.law_decree
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


def list_sections(db: Session, *, checklist_id) -> list[AdminSectionResponse]:
    rows = db.scalars(
        select(ChecklistSection).where(ChecklistSection.checklist_id == checklist_id).order_by(asc(ChecklistSection.display_order))
    ).all()
    return [_to_section_response(row) for row in rows]


def create_section(db: Session, *, checklist_id, payload: AdminSectionCreateRequest) -> AdminSectionResponse:
    section = ChecklistSection(
        checklist_id=checklist_id,
        section_code=f"SEC-{payload.order}",
        title=payload.title,
        source_ref=None,
        display_order=payload.order,
    )
    db.add(section)
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
        section.title = payload.title
    if payload.order is not None:
        section.display_order = payload.order

    db.commit()
    db.refresh(section)
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


def list_questions(db: Session, *, checklist_id, section_id) -> list[AdminQuestionResponse]:
    rows = db.scalars(
        select(ChecklistQuestion)
        .where(ChecklistQuestion.checklist_id == checklist_id, ChecklistQuestion.section_id == section_id)
        .order_by(asc(ChecklistQuestion.display_order))
    ).all()
    return [_to_question_response(row) for row in rows]


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
    return _to_question_response(question)


def create_question(db: Session, *, checklist_id, section_id, payload: AdminQuestionCreateRequest) -> AdminQuestionResponse:
    last_order = db.scalar(
        select(ChecklistQuestion.display_order)
        .where(ChecklistQuestion.section_id == section_id)
        .order_by(ChecklistQuestion.display_order.desc())
        .limit(1)
    )
    next_order = (last_order or 0) + 1

    question = ChecklistQuestion(
        checklist_id=checklist_id,
        section_id=section_id,
        question_code=payload.question_id,
        paragraph_title=None,
        legal_requirement=payload.legal_requirement,
        question_text=payload.legal_requirement,
        explanation=payload.explanation,
        expected_implementation=payload.expected_implementation,
        guidance_score_4=None,
        guidance_score_3=None,
        guidance_score_2=None,
        guidance_score_1=None,
        recommendation_template=None,
        severity=_points_to_severity(payload.points),
        report_domain=None,
        report_chapter=None,
        illustrative_image_url=None,
        note_enabled=True,
        evidence_enabled=True,
        final_score_mode=QuestionScoreMode.answer_only,
        display_order=next_order,
        is_active=True,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
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
    if payload.security_level is not None:
        question.severity = payload.security_level
    if payload.legal_requirement is not None:
        question.legal_requirement = payload.legal_requirement
        question.question_text = payload.legal_requirement
    if payload.explanation is not None:
        question.explanation = payload.explanation
    if payload.expected_implementation is not None:
        question.expected_implementation = payload.expected_implementation
    if payload.points is not None:
        question.severity = _points_to_severity(payload.points)
    if payload.order is not None:
        question.display_order = payload.order

    db.commit()
    db.refresh(question)
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
