from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class PageStatus(StrEnum):
    draft = "draft"
    published = "published"


class ContentType(StrEnum):
    hero = "hero"
    product_catalog = "product_catalog"
    faq = "faq"
    use_cases = "use_cases"
    steps = "steps"
    contact_info = "contact_info"
    legal = "legal"
    standard = "standard"


    # Frontend added content types may be extended here as needed


class SectionType(StrEnum):
    hero = "hero"
    products = "products"
    faq = "faq"
    use_cases = "use_cases"
    steps = "steps"
    contact_info = "contact_info"
    legal = "legal"
    standard = "standard"
    # Additional section types introduced by frontend design
    cards = "cards"
    cta = "cta"
    trust = "trust"
    how_it_works = "how-it-works"
    documentation_grid = "documentation-grid"
    bundles = "bundles"
    why_choose = "why-choose"


class Page(Base):
    """
    CMS Page model for managing marketing and public pages.
    Supports multiple languages with separate entries per language.
    """
    __tablename__ = "cms_pages"
    __table_args__ = (UniqueConstraint("slug", "language", name="uq_cms_pages_slug_language"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Unique identifier for the page (e.g., "home", "faq", "products")
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Language code (e.g., "cs", "en")
    language: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    
    # Page title
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # SEO meta description
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Publication status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PageStatus.draft.value)
    
    # Content type hint for the frontend (helps with rendering)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False, default=ContentType.standard.value)
    
    # Created/Updated tracking
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    updated_by: Mapped["User"] = relationship("User", foreign_keys=[updated_by_id])
    sections: Mapped[list["PageSection"]] = relationship(
        "PageSection", back_populates="page", cascade="all, delete-orphan"
    )


class PageSection(Base):
    """
    Content sections within a CMS page.
    Each section has a type and flexible JSON data field for storing structured content.
    """
    __tablename__ = "cms_page_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference to parent page
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cms_pages.id", ondelete="CASCADE"), nullable=False
    )
    
    # Section type determines how data is rendered
    section_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Order of sections on the page
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Flexible JSON data storage for section content
    # Structure depends on section_type:
    # - hero: {title, subtitle, image_url, button_text, button_link}
    # - products: {products: [{name, description, price, category, image_url}]}
    # - faq: {items: [{question, answer}]}
    # - use_cases: {items: [{icon, title, description}]}
    # - steps: {items: [{number, title, description, icon}]}
    # - contact_info: {email, phone, address, response_time}
    # - legal: {content}
    # - standard: {content}
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    page: Mapped["Page"] = relationship("Page", back_populates="sections")


class CMSImage(Base):
    """
    CMS Image management model for tracking uploaded images.
    Supports S3 or local storage.
    """
    __tablename__ = "cms_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Original filename
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # S3 key or local file path
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    
    # MIME type (e.g., "image/png")
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # File size in bytes
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Alt text for accessibility
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Who uploaded this image
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    
    # JSON field tracking which pages use this image
    # Structure: {page_ids: [uuid1, uuid2, ...]}
    used_in_pages: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    # Whether the image is active/available for use
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    uploaded_by: Mapped["User"] = relationship("User")
