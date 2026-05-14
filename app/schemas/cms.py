from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# PAGE SCHEMAS
# ============================================================================

class PageSectionBase(BaseModel):
    section_type: str = Field(
        ...,
        description=(
            "Type of section: hero, products, faq, cards, cta, trust, how-it-works, "
            "documentation-grid, bundles, why-choose, use_cases, steps, contact_info, legal, standard"
        ),
    )
    order: int = Field(default=0, description="Order of section on page")
    data: Optional[dict] = Field(default=None, description="Flexible JSON data for section content")


class PageSectionCreate(PageSectionBase):
    pass


class PageSectionCreateRequest(PageSectionCreate):
    page_id: UUID


class PageSectionUpdate(BaseModel):
    section_type: Optional[str] = None
    order: Optional[int] = None
    data: Optional[dict] = None


class PageSectionResponse(PageSectionBase):
    id: UUID
    page_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PageBase(BaseModel):
    slug: str = Field(..., description="Unique page identifier (e.g., 'home', 'faq')")
    language: str = Field(..., description="Language code (e.g., 'cs', 'en')")
    title: str = Field(..., description="Page title")
    meta_description: Optional[str] = Field(None, description="SEO meta description")
    status: str = Field(default="draft", description="Page status: draft or published")
    content_type: str = Field(default="standard", description="Content type hint for frontend")


class PageCreate(PageBase):
    pass


class PageUpdate(BaseModel):
    title: Optional[str] = None
    meta_description: Optional[str] = None
    status: Optional[str] = None
    content_type: Optional[str] = None


class PageResponse(PageBase):
    id: UUID
    created_by_id: UUID
    updated_by_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PageDetailResponse(PageResponse):
    """Full page response with sections"""
    sections: list[PageSectionResponse] = Field(default_factory=list)


class PageListResponse(BaseModel):
    """Simplified page info for list views"""
    id: UUID
    slug: str
    language: str
    title: str
    status: str
    updated_at: datetime

    class Config:
        from_attributes = True


class PagePublishToggle(BaseModel):
    """Request to toggle page publish status"""
    status: str = Field(..., description="Target status: draft or published")


# ============================================================================
# IMAGE SCHEMAS
# ============================================================================

class CMSImageBase(BaseModel):
    filename: str = Field(..., description="Original filename")
    alt_text: Optional[str] = Field(None, description="Alt text for accessibility")


class CMSImageCreate(CMSImageBase):
    pass


class CMSImageUpdate(BaseModel):
    alt_text: Optional[str] = None


class CMSImageResponse(CMSImageBase):
    id: UUID
    file_path: str
    mime_type: str
    file_size: Optional[int]
    uploaded_by_id: UUID
    is_active: bool
    used_in_pages: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CMSImageUploadResponse(CMSImageResponse):
    """Response after successful image upload"""
    file_url: Optional[str] = Field(None, description="Public URL to the image")


# ============================================================================
# BULK OPERATIONS
# ============================================================================

class BulkPageStatusUpdate(BaseModel):
    """Update status for multiple pages"""
    page_ids: list[UUID]
    status: str = Field(..., description="Target status: draft or published")


class BulkImageDelete(BaseModel):
    """Delete multiple images"""
    image_ids: list[UUID]
