from uuid import UUID

import uuid
import os
from datetime import datetime
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.schemas.assessment import (
    AssessmentAnswerResponse,
    AssessmentAnswerUpsertRequest,
    AssessmentDetailResponse,
    AssessmentSessionResponse,
    AssessmentSubmitResponse,
    StartAssessmentRequest,
)
from app.services.assessment import (
    get_current_assessment,
    get_current_assessment_detail,
    start_assessment,
    submit_assessment,
    upsert_assessment_answer,
)
from app.utils.i18n import get_language_code
from app.utils.file_upload import allowed_file, validate_file_type, get_file_size, compute_sha256, basic_malware_scan, encrypt_file_data
from app.models.assessment import AssessmentEvidenceFile, MalwareScanStatus
from app.models.media import Media, MediaType
import shutil

router = APIRouter(prefix="/assessment", tags=["assessment"])


@router.post(
    "/start",
    response_model=AssessmentSessionResponse,
    summary="Start Assessment Session",
    description=(
        "Starts or resumes an in-progress assessment for the authenticated user. "
        "Requires a paid access window for the requested checklist."
    ),
)
def start_assessment_route(
    request: StartAssessmentRequest,
    http_request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentSessionResponse:
    lang_code = get_language_code(http_request, db)
    return start_assessment(db, user=current_user, checklist_id=request.checklist_id, lang_code=lang_code)


@router.get(
    "/current",
    response_model=AssessmentSessionResponse,
    summary="Get Current Assessment",
    description=(
        "Returns the active in-progress assessment for the current user. "
        "Optional checklist_id can narrow the lookup to a specific checklist."
    ),
)
def get_current_assessment_route(
    checklist_id: UUID | None = None,
    http_request: Request = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentSessionResponse:
    lang_code = get_language_code(http_request, db) if http_request else None
    return get_current_assessment(db, user=current_user, checklist_id=checklist_id, lang_code=lang_code)


@router.get(
    "/current/detail",
    response_model=AssessmentDetailResponse,
    summary="Get Current Assessment Detail",
    description=(
        "Returns the active in-progress assessment session for the current user, "
        "along with checklist sections, questions, nested sub-questions, and current answers."
    ),
)
def get_current_assessment_detail_route(
    checklist_id: UUID | None = None,
    http_request: Request = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentDetailResponse:
    lang_code = get_language_code(http_request, db) if http_request else None
    return get_current_assessment_detail(db, user=current_user, checklist_id=checklist_id, lang_code=lang_code)


@router.put(
    "/{assessment_id}/answers",
    response_model=AssessmentAnswerResponse,
    summary="Save Assessment Answer",
    description=(
        "Creates or updates an answer for a question in an assessment. "
        "This endpoint is idempotent per assessment_id + question_id."
    ),
)
def upsert_answer_route(
    assessment_id: UUID,
    request: AssessmentAnswerUpsertRequest,
    http_request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentAnswerResponse:
    lang_code = get_language_code(http_request, db)
    return upsert_assessment_answer(
        db,
        user=current_user,
        assessment_id=assessment_id,
        question_id=request.question_id,
        answer=request.answer,
        note_text=request.note_text,
        lang_code=lang_code,
    )


@router.post(
    "/{assessment_id}/submit",
    response_model=AssessmentSubmitResponse,
    summary="Submit Assessment",
    description=(
        "Finalizes an in-progress assessment, sets submitted timestamps, and locks the session for report generation."
    ),
)
def submit_assessment_route(
    assessment_id: UUID,
    http_request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentSubmitResponse:
    lang_code = get_language_code(http_request, db)
    return submit_assessment(db, user=current_user, assessment_id=assessment_id, lang_code=lang_code)

@router.post(
    "/{assessment_id}/evidence",
    summary="Upload evidence file for assessment answer",
)
def upload_evidence_file(
    assessment_id: UUID,
    question_id: UUID,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validate extension
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="invalid_file_type")
    # Validate file type and size
    contents = file.file
    if not validate_file_type(contents, file.filename):
        raise HTTPException(status_code=400, detail="invalid_file_content")
    size = get_file_size(contents)
    if size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="file_too_large")
    
    # Determine media type
    if file.content_type.startswith("image/"):
        media_type = MediaType.image
    else:
        media_type = MediaType.document
    
    # Basic malware scan
    if not basic_malware_scan(contents):
        scan_status = MalwareScanStatus.infected
    else:
        scan_status = MalwareScanStatus.clean
    
    # Compute hash
    sha256 = compute_sha256(contents)
    
    # Read file content for encryption
    contents.seek(0)
    file_data = contents.read()
    
    # Encrypt evidence files (but not admin media)
    encrypted_data, encryption_status = encrypt_file_data(file_data)
    
    # Create media record first
    media = Media(
        filename=f"evidence_{uuid.uuid4()}{os.path.splitext(file.filename or '')[1]}",
        original_filename=file.filename or "unknown",
        mime_type=file.content_type,
        file_size_bytes=size,
        file_path="",  # Will be set by media upload route if needed
        media_type=media_type,
        sha256=sha256,
        scan_status=scan_status,
        encryption_status=encryption_status,
        uploaded_by=current_user.id,
    )
    db.add(media)
    db.flush()  # Get the media ID without committing
    
    # Save encrypted file to storage
    storage_dir = "private_uploads/assessment_evidence"
    os.makedirs(storage_dir, exist_ok=True)
    storage_key = f"{assessment_id}_{question_id}_{sha256}_{media.filename}"
    storage_path = os.path.join(storage_dir, storage_key)
    
    with open(storage_path, "wb") as out_file:
        out_file.write(encrypted_data)
    
    # Update media record with file path
    media.file_path = storage_path
    
    # Store evidence record linking to media
    evidence = AssessmentEvidenceFile(
        assessment_id=assessment_id,
        question_id=question_id,
        media_id=media.id,
        uploaded_at=datetime.utcnow(),
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    
    return {
        "id": evidence.id, 
        "media_id": media.id,
        "scan_status": media.scan_status,
        "encryption_status": media.encryption_status,
        "filename": evidence.media.original_filename
    }