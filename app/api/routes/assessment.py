from uuid import UUID

import os
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.schemas.assessment import (
    AssessmentAnswerResponse,
    AssessmentAnswerUpsertRequest,
    AssessmentSessionResponse,
    AssessmentSubmitResponse,
    StartAssessmentRequest,
)
from app.services.assessment import get_current_assessment, start_assessment, submit_assessment, upsert_assessment_answer
from app.utils.file_upload import allowed_file, validate_file_type, get_file_size, compute_sha256, basic_malware_scan
from app.models.assessment import AssessmentEvidenceFile, MalwareScanStatus
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
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentSessionResponse:
    return start_assessment(db, user=current_user, checklist_id=request.checklist_id)


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
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentSessionResponse:
    return get_current_assessment(db, user=current_user, checklist_id=checklist_id)


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
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentAnswerResponse:
    return upsert_assessment_answer(
        db,
        user=current_user,
        assessment_id=assessment_id,
        question_id=request.question_id,
        answer=request.answer,
        note_text=request.note_text,
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
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentSubmitResponse:
    return submit_assessment(db, user=current_user, assessment_id=assessment_id)


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
    if size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="file_too_large")
    # Basic malware scan
    if not basic_malware_scan(contents):
        scan_status = MalwareScanStatus.infected
    else:
        scan_status = MalwareScanStatus.clean
    # Compute hash
    sha256 = compute_sha256(contents)
    # Save file to private storage (local for now)
    storage_dir = "private_uploads/assessment_evidence"
    os.makedirs(storage_dir, exist_ok=True)
    storage_key = f"{assessment_id}_{question_id}_{sha256}_{file.filename}"
    storage_path = os.path.join(storage_dir, storage_key)
    contents.seek(0)
    with open(storage_path, "wb") as out_file:
        shutil.copyfileobj(contents, out_file)
    # Store metadata
    evidence = AssessmentEvidenceFile(
        assessment_id=assessment_id,
        question_id=question_id,
        storage_key=storage_key,
        original_filename=file.filename,
        mime_type=file.content_type,
        file_size_bytes=size,
        sha256=sha256,
        scan_status=scan_status,
        uploaded_by=current_user.id,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return {"id": evidence.id, "scan_status": evidence.scan_status, "filename": evidence.original_filename}
