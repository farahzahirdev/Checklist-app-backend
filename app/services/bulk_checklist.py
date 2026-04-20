"""Service for bulk checklist creation from parsed files."""
import uuid
from typing import Optional
from sqlalchemy import select
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
from app.schemas.bulk_checklist import (
    ColumnMapping,
    ParsedRow,
    VerifyMappingResponse,
    BulkChecklistCreateResponse,
)
from app.services.file_parser import (
    parse_file,
    get_column_value,
    FileParseError,
)


class BulkImportError(Exception):
    """Raised when bulk import validation fails."""
    pass


def _normalize_severity(severity_text: Optional[str]) -> Optional[SeverityLevel]:
    """Normalize severity text to SeverityLevel enum."""
    if not severity_text:
        return None
    
    severity_lower = str(severity_text).strip().lower()
    
    if severity_lower in ('high', 'h', '3'):
        return SeverityLevel.high
    elif severity_lower in ('medium', 'med', 'm', '2'):
        return SeverityLevel.medium
    elif severity_lower in ('low', 'l', '1'):
        return SeverityLevel.low
    else:
        return None


def _get_or_create_language(db: Session) -> Language:
    """Get default language or the first available one."""
    lang = db.scalar(select(Language).where(Language.is_default.is_(True)).limit(1))
    if not lang:
        lang = db.scalar(select(Language).limit(1))
    if not lang:
        # Create a default language if none exists
        lang = Language(code="en", name="English", is_default=True)
        db.add(lang)
        db.flush()
    return lang


def verify_mapping(
    file_content: bytes | str,
    file_name: str,
    column_mapping: ColumnMapping,
    preview_rows: int = 10,
) -> VerifyMappingResponse:
    """
    Parse file and verify column mapping without creating anything.
    Returns preview of parsed rows and validation status.
    """
    try:
        headers, rows = parse_file(file_content, file_name)
    except FileParseError as e:
        return VerifyMappingResponse(
            is_valid=False,
            total_rows=0,
            valid_rows=0,
            invalid_rows=0,
            preview_rows=[],
            column_headers=headers if 'headers' in locals() else [],
            warnings=[f"Failed to parse file: {str(e)}"],
        )
    
    if not rows:
        return VerifyMappingResponse(
            is_valid=False,
            total_rows=0,
            valid_rows=0,
            invalid_rows=0,
            preview_rows=[],
            column_headers=headers,
            warnings=["File contains no data rows"],
        )
    
    # Parse and validate rows
    parsed_rows = []
    valid_count = 0
    invalid_count = 0
    warnings = []
    seen_sections = set()
    
    for row_idx, row in enumerate(rows[:preview_rows]):
        row_number = row.get('_row_number', row_idx + 2)
        errors = []
        
        # Extract fields
        section_name = get_column_value(row, column_mapping.section_name_col, headers) or ""
        parent_q_id = get_column_value(row, column_mapping.question_id_col, headers) or ""
        child_q_id = get_column_value(row, column_mapping.child_question_col, headers)
        grandchild_q_id = get_column_value(row, column_mapping.grandchild_question_col, headers)
        legal_req = get_column_value(row, column_mapping.legal_requirement_col, headers) or ""
        question_text = get_column_value(row, column_mapping.question_text_col, headers) or ""
        severity_text = get_column_value(row, column_mapping.severity_col, headers)
        explanation = get_column_value(row, column_mapping.explanation_col, headers)
        expected_impl = get_column_value(row, column_mapping.expected_implementation_col, headers)
        
        # Validate required fields
        if not section_name:
            errors.append("Missing section name")
        else:
            seen_sections.add(section_name)
        
        if not parent_q_id:
            errors.append("Missing parent question ID")
        if not legal_req:
            errors.append("Missing legal requirement")
        if not question_text:
            errors.append("Missing question text")
        
        # Validate severity
        severity = _normalize_severity(severity_text)
        if severity_text and not severity:
            errors.append(f"Invalid severity: {severity_text}")
        
        is_valid = len(errors) == 0
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
        
        parsed_rows.append(ParsedRow(
            row_number=row_number,
            section_name=section_name,
            parent_question_id=parent_q_id,
            parent_question_text=question_text,
            child_question_id=child_q_id,
            grandchild_question_id=grandchild_q_id,
            legal_requirement=legal_req,
            severity=severity or "low",
            explanation=explanation,
            expected_implementation=expected_impl,
            is_valid=is_valid,
            errors=errors,
        ))
    
    if invalid_count > 0:
        warnings.append(f"{invalid_count} rows have validation errors")
    
    if len(rows) > preview_rows:
        warnings.append(f"Preview showing {preview_rows} of {len(rows)} total rows")
    
    return VerifyMappingResponse(
        is_valid=valid_count > 0,
        total_rows=len(rows),
        valid_rows=valid_count,
        invalid_rows=invalid_count,
        preview_rows=parsed_rows,
        column_headers=headers,
        warnings=warnings,
    )


def create_checklist_from_file(
    db: Session,
    actor: User,
    file_content: bytes | str,
    file_name: str,
    column_mapping: ColumnMapping,
    checklist_title: str,
    checklist_description: Optional[str] = None,
    checklist_type_code: str = "compliance",
    checklist_version: int = 1,
) -> BulkChecklistCreateResponse:
    """
    Parse file and create complete checklist with sections and questions.
    """
    try:
        headers, rows = parse_file(file_content, file_name)
    except FileParseError as e:
        return BulkChecklistCreateResponse(
            checklist_id=None,
            checklist_title=checklist_title,
            sections_created=0,
            questions_created=0,
            sub_questions_created=0,
            total_rows_processed=0,
            warnings=[f"File parsing failed: {str(e)}"],
            status="failed",
            message=f"Failed to parse file: {str(e)}",
        )
    
    if not rows:
        return BulkChecklistCreateResponse(
            checklist_id=None,
            checklist_title=checklist_title,
            sections_created=0,
            questions_created=0,
            sub_questions_created=0,
            total_rows_processed=0,
            warnings=["File contains no data rows"],
            status="failed",
            message="File contains no data rows",
        )
    
    try:
        # Create or get checklist type
        checklist_type = db.scalar(
            select(ChecklistType).where(ChecklistType.code == checklist_type_code)
        )
        if not checklist_type:
            checklist_type = ChecklistType(
                code=checklist_type_code,
                name=checklist_title,
                description=checklist_description,
                is_active=True,
            )
            db.add(checklist_type)
            db.flush()
        
        # Create checklist
        checklist = Checklist(
            checklist_type_id=checklist_type.id,
            version=checklist_version,
            status=ChecklistStatus.draft,
            created_by=actor.id,
            updated_by=actor.id,
        )
        db.add(checklist)
        db.flush()
        
        # Get default language
        language = _get_or_create_language(db)
        
        # Add checklist translation
        db.add(ChecklistTranslation(
            checklist_id=checklist.id,
            lang_code="en",
            title=checklist_title,
            description=checklist_description or "",
        ))
        
        # Track created items and sections
        sections_map = {}  # section_name -> section_id
        questions_map = {}  # parent_q_id -> question_id (for linking children)
        sections_created = 0
        questions_created = 0
        sub_questions_created = 0
        warnings = []
        skipped_rows = 0
        
        # Process rows
        for row_idx, row in enumerate(rows):
            row_number = row.get('_row_number', row_idx + 2)
            
            try:
                # Extract fields
                section_name = get_column_value(row, column_mapping.section_name_col, headers) or ""
                parent_q_id = get_column_value(row, column_mapping.question_id_col, headers) or ""
                child_q_id = get_column_value(row, column_mapping.child_question_col, headers)
                grandchild_q_id = get_column_value(row, column_mapping.grandchild_question_col, headers)
                legal_req = get_column_value(row, column_mapping.legal_requirement_col, headers) or ""
                question_text = get_column_value(row, column_mapping.question_text_col, headers) or ""
                severity_text = get_column_value(row, column_mapping.severity_col, headers)
                explanation = get_column_value(row, column_mapping.explanation_col, headers)
                expected_impl = get_column_value(row, column_mapping.expected_implementation_col, headers)
                source_ref = get_column_value(row, column_mapping.source_ref_col, headers)
                
                # Validate required fields
                if not section_name or not parent_q_id or not legal_req or not question_text:
                    skipped_rows += 1
                    warnings.append(f"Row {row_number}: Skipped - missing required fields")
                    continue
                
                # Normalize severity
                severity = _normalize_severity(severity_text) or SeverityLevel.low
                
                # Create or get section
                if section_name not in sections_map:
                    display_order = len(sections_map) + 1
                    section = ChecklistSection(
                        checklist_id=checklist.id,
                        section_code=f"SEC-{display_order}",
                        source_ref=source_ref,
                        display_order=display_order,
                    )
                    db.add(section)
                    db.flush()
                    
                    # Add section translation
                    db.add(ChecklistSectionTranslation(
                        section_id=section.id,
                        lang_code="en",
                        title=section_name,
                    ))
                    
                    sections_map[section_name] = section.id
                    sections_created += 1
                
                section_id = sections_map[section_name]
                
                # Create parent question if this is a new parent ID
                parent_question_id = None
                if parent_q_id not in questions_map:
                    parent_question = ChecklistQuestion(
                        checklist_id=checklist.id,
                        section_id=section_id,
                        parent_question_id=None,
                        question_code=parent_q_id,
                        severity=severity,
                        report_domain=None,
                        report_chapter=None,
                        illustrative_image_url=None,
                        note_for_user=None,
                        note_enabled=True,
                        evidence_enabled=True,
                        display_order=len([q for q in db.scalars(
                            select(ChecklistQuestion).where(
                                ChecklistQuestion.section_id == section_id
                            )
                        ).all()]) + 1,
                        is_active=True,
                    )
                    db.add(parent_question)
                    db.flush()
                    
                    # Add question translation
                    db.add(ChecklistQuestionTranslation(
                        question_id=parent_question.id,
                        lang_code="en",
                        question_text=question_text,
                        explanation=explanation,
                        expected_implementation=expected_impl,
                    ))
                    
                    questions_map[parent_q_id] = parent_question.id
                    questions_created += 1
                else:
                    parent_question_id = questions_map[parent_q_id]
                
                # Create child question if specified
                if child_q_id:
                    child_key = f"{parent_q_id}|{child_q_id}"
                    if child_key not in questions_map:
                        child_question = ChecklistQuestion(
                            checklist_id=checklist.id,
                            section_id=section_id,
                            parent_question_id=questions_map[parent_q_id],
                            question_code=child_q_id,
                            severity=severity,
                            report_domain=None,
                            report_chapter=None,
                            illustrative_image_url=None,
                            note_for_user=None,
                            note_enabled=True,
                            evidence_enabled=True,
                            display_order=len([q for q in db.scalars(
                                select(ChecklistQuestion).where(
                                    ChecklistQuestion.section_id == section_id
                                )
                            ).all()]) + 1,
                            is_active=True,
                        )
                        db.add(child_question)
                        db.flush()
                        
                        db.add(ChecklistQuestionTranslation(
                            question_id=child_question.id,
                            lang_code="en",
                            question_text=question_text,
                            explanation=explanation,
                            expected_implementation=expected_impl,
                        ))
                        
                        questions_map[child_key] = child_question.id
                        sub_questions_created += 1
                
                # Create grandchild question if specified
                if grandchild_q_id and child_q_id:
                    grandchild_key = f"{parent_q_id}|{child_q_id}|{grandchild_q_id}"
                    if grandchild_key not in questions_map:
                        child_parent_id = questions_map.get(f"{parent_q_id}|{child_q_id}")
                        if child_parent_id:
                            grandchild_question = ChecklistQuestion(
                                checklist_id=checklist.id,
                                section_id=section_id,
                                parent_question_id=child_parent_id,
                                question_code=grandchild_q_id,
                                severity=severity,
                                report_domain=None,
                                report_chapter=None,
                                illustrative_image_url=None,
                                note_for_user=None,
                                note_enabled=True,
                                evidence_enabled=True,
                                display_order=len([q for q in db.scalars(
                                    select(ChecklistQuestion).where(
                                        ChecklistQuestion.section_id == section_id
                                    )
                                ).all()]) + 1,
                                is_active=True,
                            )
                            db.add(grandchild_question)
                            db.flush()
                            
                            db.add(ChecklistQuestionTranslation(
                                question_id=grandchild_question.id,
                                lang_code="en",
                                question_text=question_text,
                                explanation=explanation,
                                expected_implementation=expected_impl,
                            ))
                            
                            questions_map[grandchild_key] = grandchild_question.id
                            sub_questions_created += 1
                
            except Exception as e:
                skipped_rows += 1
                warnings.append(f"Row {row_number}: {str(e)}")
                continue
        
        db.commit()
        db.refresh(checklist)
        
        status = "success"
        message = f"Created checklist with {sections_created} sections and {questions_created + sub_questions_created} questions"
        
        if warnings:
            status = "success_with_warnings"
            message += f" ({skipped_rows} rows skipped with warnings)"
        
        return BulkChecklistCreateResponse(
            checklist_id=checklist.id,
            checklist_title=checklist_title,
            sections_created=sections_created,
            questions_created=questions_created,
            sub_questions_created=sub_questions_created,
            total_rows_processed=len(rows),
            warnings=warnings,
            status=status,
            message=message,
        )
        
    except Exception as e:
        db.rollback()
        return BulkChecklistCreateResponse(
            checklist_id=None,
            checklist_title=checklist_title,
            sections_created=0,
            questions_created=0,
            sub_questions_created=0,
            total_rows_processed=len(rows),
            warnings=[str(e)],
            status="failed",
            message=f"Failed to create checklist: {str(e)}",
        )
