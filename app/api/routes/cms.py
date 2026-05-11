from uuid import UUID, uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile, Request
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_admin_only, get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.cms import (
    PageCreate, PageUpdate, PageDetailResponse, PageListResponse,
    PageSectionCreate, PageSectionUpdate, PageSectionResponse,
    CMSImageCreate, CMSImageResponse, CMSImageUpdate, CMSImageUploadResponse,
    PagePublishToggle
)
from app.services.cms_service import CMSService
from app.utils.i18n import get_language_code
from app.utils.s3_upload import upload_to_s3, validate_upload_file
from app.models.cms import CMSImage

router = APIRouter(prefix="/api/cms", tags=["cms"])


# ============================================================================
# PAGE ENDPOINTS
# ============================================================================

@router.get(
    "/pages",
    response_model=dict,
    summary="List CMS Pages",
    description="Admin only: List all CMS pages with optional filtering by language and status."
)
def list_pages(
    language: Optional[str] = Query(None, description="Filter by language code"),
    status: Optional[str] = Query(None, description="Filter by status (draft/published)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """List all CMS pages for administration."""
    cms_service = CMSService(db)
    pages, total = cms_service.list_pages(language=language, status=status, skip=skip, limit=limit)
    
    return {
        "items": [
            PageListResponse.model_validate(p).__dict__ for p in pages
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get(
    "/pages/{identifier}",
    response_model=PageDetailResponse,
    summary="Get Page Details",
    description="Get full page details including all sections. Public endpoint if page is published."
)
def get_page(
    identifier: str,
    language: Optional[str] = Query(None, description="Language code (defaults to 'en')"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Get a page by ID or slug and language."""
    if not language:
        language = "en"
    
    cms_service = CMSService(db)
    is_admin = current_user and current_user.role == "admin"
    
    # Try to parse as UUID first
    try:
        page_id = uuid.UUID(identifier)
        page = cms_service.get_page_by_id(page_id, language, include_drafts=is_admin)
    except ValueError:
        # Not a UUID, treat as slug
        page = cms_service.get_page_by_slug(identifier, language, include_drafts=is_admin)
    
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page '{identifier}' not found"
        )
    
    # Build response with sections
    sections = [
        PageSectionResponse.model_validate(s).__dict__ for s in page.sections
    ]
    
    response = PageDetailResponse.model_validate(page).__dict__
    response["sections"] = sections
    
    return response


@router.post(
    "/pages",
    response_model=PageDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create CMS Page",
    description="Admin only: Create a new CMS page."
)
def create_page(
    data: PageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """Create a new CMS page."""
    cms_service = CMSService(db)
    
    try:
        page = cms_service.create_page(data, current_user.id)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    response = PageDetailResponse.model_validate(page).__dict__
    response["sections"] = []
    
    return response


@router.put(
    "/pages/{page_id}",
    response_model=PageDetailResponse,
    summary="Update CMS Page",
    description="Admin only: Update page metadata (title, description, etc)."
)
def update_page(
    page_id: UUID,
    data: PageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """Update an existing CMS page."""
    cms_service = CMSService(db)
    
    try:
        page = cms_service.update_page(page_id, data, current_user.id)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    # Refresh to get sections
    db.refresh(page)
    
    response = PageDetailResponse.model_validate(page).__dict__
    response["sections"] = [
        PageSectionResponse.model_validate(s).__dict__ for s in page.sections
    ]
    
    return response


@router.patch(
    "/pages/{page_id}/publish",
    response_model=PageDetailResponse,
    summary="Publish/Unpublish Page",
    description="Admin only: Toggle page between draft and published status."
)
def toggle_publish_page(
    page_id: UUID,
    data: PagePublishToggle,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """Publish or unpublish a page."""
    cms_service = CMSService(db)
    
    try:
        page = cms_service.update_page(
            page_id,
            PageUpdate(status=data.status),
            current_user.id
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    db.refresh(page)
    
    response = PageDetailResponse.model_validate(page).__dict__
    response["sections"] = [
        PageSectionResponse.model_validate(s).__dict__ for s in page.sections
    ]
    
    return response


@router.delete(
    "/pages/{page_id}",
    summary="Delete CMS Page",
    description="Admin only: Delete a page and all its sections.",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_page(
    page_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """Delete a CMS page."""
    cms_service = CMSService(db)
    
    if not cms_service.delete_page(page_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page with ID {page_id} not found"
        )
    
    db.commit()
    return None


# ============================================================================
# PAGE SECTION ENDPOINTS
# ============================================================================

@router.post(
    "/sections",
    response_model=PageSectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Page Section",
    description="Admin only: Create a new section within a page."
)
def create_section(
    page_id: UUID,
    data: PageSectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """Create a new section for a page."""
    cms_service = CMSService(db)
    
    try:
        section = cms_service.create_section(page_id, data)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    return PageSectionResponse.model_validate(section).__dict__


@router.put(
    "/sections/{section_id}",
    response_model=PageSectionResponse,
    summary="Update Section",
    description="Admin only: Update a page section."
)
def update_section(
    section_id: UUID,
    data: PageSectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """Update a page section."""
    cms_service = CMSService(db)
    
    try:
        section = cms_service.update_section(section_id, data)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    return PageSectionResponse.model_validate(section).__dict__


@router.delete(
    "/sections/{section_id}",
    summary="Delete Section",
    description="Admin only: Delete a page section.",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_section(
    section_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """Delete a page section."""
    cms_service = CMSService(db)
    
    if not cms_service.delete_section(section_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section with ID {section_id} not found"
        )
    
    db.commit()
    return None


# ============================================================================
# IMAGE ENDPOINTS
# ============================================================================

@router.get(
    "/images",
    response_model=dict,
    summary="List CMS Images",
    description="Admin only: List all uploaded CMS images."
)
def list_images(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """List all CMS images."""
    cms_service = CMSService(db)
    images, total = cms_service.list_images(skip=skip, limit=limit, active_only=True)
    
    return {
        "items": [
            CMSImageResponse.model_validate(img).__dict__ for img in images
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post(
    "/images/upload",
    response_model=CMSImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Image",
    description="Admin only: Upload a new image for use in CMS pages."
)
async def upload_image(
    file: UploadFile = File(...),
    alt_text: str = Query("", description="Alt text for accessibility"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """Upload a new image for CMS."""
    # Validate file
    try:
        await validate_upload_file(file, max_file_size_mb=10)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Upload to S3 or local storage
    try:
        file_path, file_size = await upload_to_s3(file)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )
    
    # Create image record
    cms_service = CMSService(db)
    image_data = CMSImageCreate(
        filename=file.filename or "image",
        alt_text=alt_text if alt_text else None
    )
    
    image = cms_service.create_image(
        image_data,
        file_path=file_path,
        mime_type=file.content_type or "image/png",
        file_size=file_size,
        user_id=current_user.id
    )
    db.commit()
    
    # Build response with file URL
    response = CMSImageResponse.model_validate(image).__dict__
    response["file_url"] = f"https://{file_path}"  # Or construct proper S3/local URL
    
    return response


@router.put(
    "/images/{image_id}",
    response_model=CMSImageResponse,
    summary="Update Image Metadata",
    description="Admin only: Update image alt text or other metadata."
)
def update_image(
    image_id: UUID,
    data: CMSImageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """Update image metadata."""
    cms_service = CMSService(db)
    
    try:
        image = cms_service.update_image(image_id, data)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    return CMSImageResponse.model_validate(image).__dict__


@router.delete(
    "/images/{image_id}",
    summary="Delete Image",
    description="Admin only: Soft delete an image (mark as inactive).",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only())
):
    """Delete an image."""
    cms_service = CMSService(db)
    
    if not cms_service.delete_image(image_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image with ID {image_id} not found"
        )
    
    db.commit()
    return None
