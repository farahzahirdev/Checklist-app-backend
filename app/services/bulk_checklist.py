"""Service for bulk checklist creation from parsed files."""
import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.checklist import (
    Checklist,
    ChecklistQuestion,
    ChecklistQuestionAnswerOption,
    ChecklistQuestionTranslation,
    ChecklistSection,
    ChecklistSectionTranslation,
    ChecklistStatus,
    ChecklistType,
    ChecklistTranslation,
    SeverityLevel,
)
import re
import uuid
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
from app.utils.audit_logger import AuditLogger

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
        raw_question_id = get_column_value(row, column_mapping.question_id_col, headers) or ""
        child_q_id = get_column_value(row, column_mapping.child_question_col, headers)
        grandchild_q_id = get_column_value(row, column_mapping.grandchild_question_col, headers)
        legal_req = get_column_value(row, column_mapping.legal_requirement_col, headers) or ""
        question_text = get_column_value(row, column_mapping.question_text_col, headers) or ""
        severity_text = get_column_value(row, column_mapping.severity_col, headers)
        explanation = get_column_value(row, column_mapping.explanation_col, headers)
        expected_impl = get_column_value(row, column_mapping.expected_implementation_col, headers)
        
        # Parse hierarchical question ID from single column (same logic as creation function)
        parent_q_id = ""
        if raw_question_id:
            # Check if it's a sub-question like "a)", "b)", "c)"
            import re
            if re.match(r'^[a-z]\)$', raw_question_id.strip()):
                # This is a sub-question, we need to find the parent
                # Look backwards in processed rows to find the last parent question
                child_q_id = raw_question_id.strip()
                # We'll find the parent later
            else:
                # This is a parent question
                parent_q_id = raw_question_id.strip()
                child_q_id = None
        
        # Skip header rows (rows that have section name but no actual content)
        if section_name and not legal_req and not question_text and (parent_q_id or child_q_id):
            # This looks like a header row, skip it
            continue
        
        # Validate required fields
        if not section_name:
            errors.append("Missing section name")
        else:
            seen_sections.add(section_name)
        
        # For hierarchical questions, if we have child_q_id but no parent_q_id,
        # find the most recent parent question in the same section
        if not parent_q_id and child_q_id:
            # Look backwards to find the last parent question in this section
            found_parent = False
            for prev_row_idx in range(row_idx - 1, -1, -1):
                prev_row = rows[prev_row_idx]
                prev_section = get_column_value(prev_row, column_mapping.section_name_col, headers) or ""
                prev_raw_q_id = get_column_value(prev_row, column_mapping.question_id_col, headers) or ""
                prev_legal_req = get_column_value(prev_row, column_mapping.legal_requirement_col, headers) or ""
                prev_question_text = get_column_value(prev_row, column_mapping.question_text_col, headers) or ""
                
                # Skip header rows and rows without actual content
                if prev_section and not prev_legal_req and not prev_question_text and (prev_raw_q_id or get_column_value(prev_row, column_mapping.child_question_col, headers)):
                    continue
                
                if prev_section == section_name and prev_raw_q_id:
                    # Check if previous row was a parent question (not a sub-question)
                    import re
                    if not re.match(r'^[a-z]\)$', prev_raw_q_id.strip()):
                        parent_q_id = prev_raw_q_id.strip()
                        found_parent = True
                        break
            
            if not found_parent:
                errors.append("Missing parent question ID")
        elif not parent_q_id:
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
    actor: User | int,
    file_content: bytes | str,
    file_name: str,
    column_mapping: ColumnMapping,
    checklist_title: str,
    checklist_description: Optional[str] = None,
    checklist_type_code: str = "compliance",
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
        # Create unique checklist type for each bulk import to prevent duplicates
        checklist_type = _get_or_create_unique_checklist_type(db, checklist_title, checklist_description or "")
        
        actor_id = actor.id if hasattr(actor, "id") else actor

        # Create checklist
        checklist = Checklist(
            checklist_type_id=checklist_type.id,
            version="1.0",  # Always start with version 1.0 (same as admin checklist service)
            status=ChecklistStatus.draft,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(checklist)
        db.flush()
        
        # Get default language
        language = _get_or_create_language(db)
        
        # Add checklist translation
        db.add(ChecklistTranslation(
            checklist_id=checklist.id,
            language_id=language.id,
            title=checklist_title,
            description=checklist_description or "",
        ))
        
        # Track created items and sections

        # Helper for answer options with fixed labels
        def build_answer_options(row):
            answer_options = []
            # Fixed labels as requested: Yes=4pts, Maybe=3pts, Sure=2pts, No=1pts
            fixed_labels = {4: "Yes", 3: "Maybe", 2: "Sure", 1: "No"}
            
            for score, col_key in zip([4, 3, 2, 1], [
                column_mapping.guidance_score_4_col,
                column_mapping.guidance_score_3_col,
                column_mapping.guidance_score_2_col,
                column_mapping.guidance_score_1_col,
            ]):
                desc = row.get(col_key) if col_key else None
                # Use fixed label, CSV content as description
                label = fixed_labels.get(score, f"Score {score}")
                answer_options.append({
                    "position": score,
                    "label": label,
                    "score": score,
                    "description": desc,
                })
            return answer_options

        # ...existing code...
        sections_map = {}  # section_name -> section_id
        questions_map = {}  # section_id -> {parent_q_id -> question_id} (section-aware mapping)
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
                raw_question_id = get_column_value(row, column_mapping.question_id_col, headers) or ""
                child_q_id = get_column_value(row, column_mapping.child_question_col, headers)
                grandchild_q_id = get_column_value(row, column_mapping.grandchild_question_col, headers)
                legal_req = get_column_value(row, column_mapping.legal_requirement_col, headers) or ""
                question_text = get_column_value(row, column_mapping.question_text_col, headers) or ""
                severity_text = get_column_value(row, column_mapping.severity_col, headers)
                explanation = get_column_value(row, column_mapping.explanation_col, headers)
                expected_impl = get_column_value(row, column_mapping.expected_implementation_col, headers)
                source_ref = get_column_value(row, column_mapping.source_ref_col, headers)
                
                # Parse hierarchical question ID from single column
                parent_q_id = ""
                if raw_question_id:
                    # Check if it's a sub-question like "a)", "b)", "c)"
                    import re
                    if re.match(r'^[a-z]\)$', raw_question_id.strip()):
                        # This is a sub-question, we need to find the parent
                        # Look backwards in processed rows to find the last parent question
                        child_q_id = raw_question_id.strip()
                        # We'll find the parent later
                    else:
                        # This is a parent question
                        parent_q_id = raw_question_id.strip()
                        child_q_id = None
                
                # Skip header rows (rows that have section name but no actual content)
                if section_name and not legal_req and not question_text and (parent_q_id or child_q_id):
                    # This looks like a header row, skip it
                    skipped_rows += 1
                    warnings.append(f"Row {row_number}: Skipped - header row")
                    continue
                
                # Validate required fields - allow hierarchical questions
                if not section_name or not legal_req or not question_text:
                    skipped_rows += 1
                    warnings.append(f"Row {row_number}: Skipped - missing required fields")
                    continue
                
                # For hierarchical questions, if we have child_q_id but no parent_q_id,
                # find the most recent parent question in the same section
                if not parent_q_id and child_q_id:
                    # Look backwards to find the last parent question in this section
                    found_parent = False
                    for prev_row_idx in range(row_idx - 1, -1, -1):
                        prev_row = rows[prev_row_idx]
                        prev_section = get_column_value(prev_row, column_mapping.section_name_col, headers) or ""
                        prev_raw_q_id = get_column_value(prev_row, column_mapping.question_id_col, headers) or ""
                        prev_legal_req = get_column_value(prev_row, column_mapping.legal_requirement_col, headers) or ""
                        prev_question_text = get_column_value(prev_row, column_mapping.question_text_col, headers) or ""
                        
                        # Skip header rows and rows without actual content
                        if prev_section and not prev_legal_req and not prev_question_text and (prev_raw_q_id or get_column_value(prev_row, column_mapping.child_question_col, headers)):
                            continue
                        
                        if prev_section == section_name and prev_raw_q_id:
                            # Check if previous row was a parent question (not a sub-question)
                            import re
                            if not re.match(r'^[a-z]\)$', prev_raw_q_id.strip()):
                                parent_q_id = prev_raw_q_id.strip()
                                found_parent = True
                                break
                    
                    if not found_parent:
                        skipped_rows += 1
                        warnings.append(f"Row {row_number}: Skipped - could not find parent question for sub-question {child_q_id}")
                        continue
                elif not parent_q_id:
                    skipped_rows += 1
                    warnings.append(f"Row {row_number}: Skipped - missing parent question ID")
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
                    db.add(ChecklistSectionTranslation(
                        section_id=section.id,
                        language_id=language.id,
                        title=section_name,
                    ))
                    sections_map[section_name] = section.id
                    sections_created += 1
                section_id = sections_map[section_name]

                # Initialize section-specific questions map if not exists
                if section_id not in questions_map:
                    questions_map[section_id] = {}

                # Build answer options for this row
                answer_options = build_answer_options(row)
                if not any(opt["description"] for opt in answer_options):
                    warnings.append(f"Row {row_number}: No answer guidance provided for any score column.")

                # Create parent question if this is a new parent ID
                parent_question_id = None
                if parent_q_id not in questions_map[section_id]:
                    parent_question = ChecklistQuestion(
                        checklist_id=checklist.id,
                        section_id=section_id,
                        parent_question_id=None,
                        question_code=parent_q_id,
                        audit_type="compliance",
                        points=1,
                        answer_logic="answer_only",
                        severity=severity,
                        report_domain=None,
                        report_chapter=None,
                        illustrative_image_id=None,
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
                    db.add(ChecklistQuestionTranslation(
                        question_id=parent_question.id,
                        language_id=language.id,
                        question_text=question_text,
                        legal_requirement_title="",  # Empty title as requested
                        legal_requirement_description=legal_req,  # Store text in description
                        explanation=explanation,
                        expected_implementation=expected_impl,
                    ))
                    # Add answer options for parent question
                    for opt in answer_options:
                        db.add(ChecklistQuestionAnswerOption(
                            question_id=parent_question.id,
                            position=opt["position"],
                            label=opt["label"],
                            score=opt["score"],
                            description=opt["description"],
                        ))
                    questions_map[section_id][parent_q_id] = parent_question.id
                    questions_created += 1
                else:
                    parent_question_id = questions_map[section_id][parent_q_id]

                # Create child question if specified
                if child_q_id:
                    child_key = f"{parent_q_id}|{child_q_id}"
                    if child_key not in questions_map[section_id]:
                        child_question = ChecklistQuestion(
                            checklist_id=checklist.id,
                            section_id=section_id,
                            parent_question_id=questions_map[section_id][parent_q_id],
                            question_code=child_q_id,  # Back to simple: "a)", "b)", "c)"
                            audit_type="compliance",
                            points=1,
                            answer_logic="answer_only",
                            severity=severity,
                            report_domain=None,
                            report_chapter=None,
                            illustrative_image_id=None,
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
                            language_id=language.id,
                            question_text=question_text,
                            legal_requirement_title="",  # Empty title as requested
                            legal_requirement_description=legal_req,  # Store text in description
                            explanation=explanation,
                            expected_implementation=expected_impl,
                        ))
                        # Add answer options for child question
                        for opt in answer_options:
                            db.add(ChecklistQuestionAnswerOption(
                                question_id=child_question.id,
                                position=opt["position"],
                                label=opt["label"],
                                score=opt["score"],
                                description=opt["description"],
                            ))
                        questions_map[section_id][child_key] = child_question.id
                        sub_questions_created += 1

                # Create grandchild question if specified
                if grandchild_q_id and child_q_id:
                    grandchild_key = f"{parent_q_id}|{child_q_id}|{grandchild_q_id}"
                    if grandchild_key not in questions_map[section_id]:
                        child_parent_id = questions_map[section_id].get(f"{parent_q_id}|{child_q_id}")
                        if child_parent_id:
                            grandchild_question = ChecklistQuestion(
                                checklist_id=checklist.id,
                                section_id=section_id,
                                parent_question_id=child_parent_id,
                                question_code=grandchild_q_id,  # Back to simple: "i)", "ii)", etc.
                                audit_type="compliance",
                                points=1,
                                answer_logic="answer_only",
                                severity=severity,
                                report_domain=None,
                                report_chapter=None,
                                illustrative_image_id=None,
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
                                language_id=language.id,
                                question_text=question_text,
                                legal_requirement_title="",  # Empty title as requested
                                legal_requirement_description=legal_req,  # Store text in description
                                explanation=explanation,
                                expected_implementation=expected_impl,
                            ))
                            # Add answer options for grandchild question
                            for opt in answer_options:
                                db.add(ChecklistQuestionAnswerOption(
                                    question_id=grandchild_question.id,
                                    position=opt["position"],
                                    label=opt["label"],
                                    score=opt["score"],
                                    description=opt["description"],
                                ))
                            questions_map[section_id][grandchild_key] = grandchild_question.id
                            sub_questions_created += 1
                
            except Exception as e:
                skipped_rows += 1
                warnings.append(f"Row {row_number}: {str(e)}")
                continue
        
        db.commit()
        db.refresh(checklist)
        
        # Create Stripe product for checklist
        try:
            from app.services.stripe_products import create_stripe_product_for_checklist
            stripe_product_id = create_stripe_product_for_checklist(
                db,
                checklist_id=checklist.id,
                title=checklist_title,
                description=checklist_description,
            )
            print(f"Created Stripe product {stripe_product_id} for bulk checklist {checklist.id}")
        except Exception as e:
            # Log error but don't fail checklist creation
            print(f"Error creating Stripe product for bulk checklist {checklist.id}: {e}")
        
        # Add audit logging for bulk checklist creation
        try:
            AuditLogger.log_checklist_action(
                db=db,
                actor_user_id=actor_id,
                action="checklist_create",
                target_id=checklist.id,
                before_json=None,
                after_json={
                    "title": checklist_title,
                    "sections_created": sections_created,
                    "questions_created": questions_created,
                    "sub_questions_created": sub_questions_created,
                    "file_name": file_name
                },
                changes_summary=f"Bulk imported checklist: {checklist_title} ({sections_created} sections, {questions_created + sub_questions_created} questions)"
            )
        except Exception as e:
            # Log error but don't fail checklist creation
            print(f"Error creating audit log for bulk checklist {checklist.id}: {e}")
        
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
