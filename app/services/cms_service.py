from __future__ import annotations

import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.cms import Page, PageSection, CMSImage, PageStatus
from app.models.user import User
from app.schemas.cms import (
    PageCreate, PageUpdate, PageDetailResponse, PageListResponse,
    PageSectionCreate, PageSectionUpdate,
    CMSImageCreate, CMSImageUpdate, CMSImageResponse
)
from app.utils.audit_logger import AuditLogger


class CMSService:
    """Service layer for CMS operations"""

    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger()

    # ========================================================================
    # PAGE OPERATIONS
    # ========================================================================

    def get_page_by_slug(
        self,
        slug: str,
        language: str,
        include_drafts: bool = False
    ) -> Optional[Page]:
        """
        Get a page by slug and language.
        
        Args:
            slug: Page slug (e.g., 'home', 'faq')
            language: Language code (e.g., 'cs', 'en')
            include_drafts: If False, only returns published pages
        
        Returns:
            Page object or None if not found
        """
        query = select(Page).where(
            Page.slug == slug,
            Page.language == language
        )
        
        if not include_drafts:
            query = query.where(Page.status == PageStatus.published.value)
        
        return self.db.scalar(query)

    def get_page_by_id(
        self,
        page_id: uuid.UUID,
        language: str,
        include_drafts: bool = False
    ) -> Optional[Page]:
        """
        Get a page by ID and language.
        
        Args:
            page_id: Page ID
            language: Language code (e.g., 'cs', 'en')
            include_drafts: If False, only returns published pages
        
        Returns:
            Page object or None if not found
        """
        query = select(Page).where(
            Page.id == page_id,
            Page.language == language
        )
        
        if not include_drafts:
            query = query.where(Page.status == PageStatus.published.value)
        
        return self.db.scalar(query)

    def list_pages(
        self,
        language: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[list[Page], int]:
        """
        List all pages with optional filtering.
        
        Args:
            language: Filter by language code
            status: Filter by status (draft/published)
            skip: Number of records to skip
            limit: Maximum number of records to return
        
        Returns:
            Tuple of (pages list, total count)
        """
        query = select(Page)
        count_query = select(func.count(Page.id))
        
        if language:
            query = query.where(Page.language == language)
            count_query = count_query.where(Page.language == language)
        
        if status:
            query = query.where(Page.status == status)
            count_query = count_query.where(Page.status == status)
        
        # Get total count
        total = self.db.scalar(count_query)
        
        # Apply pagination
        query = query.order_by(Page.updated_at.desc()).offset(skip).limit(limit)
        
        pages = self.db.scalars(query).all()
        return pages, total

    def create_page(
        self,
        data: PageCreate,
        user_id: uuid.UUID
    ) -> Page:
        """
        Create a new page.
        
        Args:
            data: Page creation data
            user_id: ID of user creating the page
        
        Returns:
            Created Page object
        """
        # Check if page already exists for this slug+language combination
        existing = self.get_page_by_slug(data.slug, data.language, include_drafts=True)
        if existing:
            raise ValueError(f"Page with slug '{data.slug}' and language '{data.language}' already exists")
        
        page = Page(
            slug=data.slug,
            language=data.language,
            title=data.title,
            meta_description=data.meta_description,
            status=data.status,
            content_type=data.content_type,
            created_by_id=user_id,
            updated_by_id=user_id
        )
        
        self.db.add(page)
        self.db.flush()  # Get the ID without committing
        
        # Log the action
        self.audit_logger.log_system_action(
            db=self.db,
            action="cms_page_create",
            actor_user_id=user_id,
            after_data={"title": data.title, "slug": data.slug},
            changes_summary=f"Created CMS page: {data.title}"
        )
        
        return page

    def update_page(
        self,
        page_id: uuid.UUID,
        data: PageUpdate,
        user_id: uuid.UUID
    ) -> Page:
        """
        Update an existing page.
        
        Args:
            page_id: ID of page to update
            data: Page update data
            user_id: ID of user updating the page
        
        Returns:
            Updated Page object
        """
        page = self.db.scalar(select(Page).where(Page.id == page_id))
        if not page:
            raise ValueError(f"Page with ID {page_id} not found")
        
        # Track changes for audit log
        changes = {}
        
        if data.title is not None and data.title != page.title:
            changes["title"] = {"old": page.title, "new": data.title}
            page.title = data.title
        
        if data.meta_description is not None and data.meta_description != page.meta_description:
            changes["meta_description"] = {"old": page.meta_description, "new": data.meta_description}
            page.meta_description = data.meta_description
        
        if data.status is not None and data.status != page.status:
            changes["status"] = {"old": page.status, "new": data.status}
            page.status = data.status
        
        if data.content_type is not None and data.content_type != page.content_type:
            changes["content_type"] = {"old": page.content_type, "new": data.content_type}
            page.content_type = data.content_type
        
        page.updated_by_id = user_id
        
        self.db.flush()
        
        # Log the action
        if changes:
            self.audit_logger.log_system_action(
                db=self.db,
                action="cms_page_update",
                actor_user_id=user_id,
                before_data={"title": page.title},
                after_data={"title": data.title or page.title},
                changes_summary=f"Updated CMS page: {page.title}"
            )
        
        return page

    def delete_page(self, page_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """
        Delete a page and its sections.
        
        Args:
            page_id: ID of page to delete
            user_id: ID of user deleting the page
        
        Returns:
            True if deleted, False if not found
        """
        page = self.db.scalar(select(Page).where(Page.id == page_id))
        if not page:
            return False
        
        # Log the action
        self.audit_logger.log_system_action(
            db=self.db,
            action="cms_page_delete",
            actor_user_id=user_id,
            after_data={"deleted": page.title},
            changes_summary=f"Deleted CMS page: {page.title}"
        )
        
        self.db.delete(page)
        return True

    def publish_page(self, page_id: uuid.UUID, user_id: uuid.UUID) -> Page:
        """
        Publish a draft page.
        
        Args:
            page_id: ID of page to publish
            user_id: ID of user publishing the page
        
        Returns:
            Updated Page object
        """
        return self.update_page(
            page_id,
            PageUpdate(status=PageStatus.published.value),
            user_id
        )

    def unpublish_page(self, page_id: uuid.UUID, user_id: uuid.UUID) -> Page:
        """
        Unpublish a page (revert to draft).
        
        Args:
            page_id: ID of page to unpublish
            user_id: ID of user unpublishing the page
        
        Returns:
            Updated Page object
        """
        return self.update_page(
            page_id,
            PageUpdate(status=PageStatus.draft.value),
            user_id
        )

    # ========================================================================
    # PAGE SECTION OPERATIONS
    # ========================================================================

    def create_section(
        self,
        page_id: uuid.UUID,
        data: PageSectionCreate
    ) -> PageSection:
        """
        Create a new section for a page.
        
        Args:
            page_id: ID of parent page
            data: Section creation data
        
        Returns:
            Created PageSection object
        """
        # Verify page exists
        page = self.db.scalar(select(Page).where(Page.id == page_id))
        if not page:
            raise ValueError(f"Page with ID {page_id} not found")
        
        section = PageSection(
            page_id=page_id,
            section_type=data.section_type,
            order=data.order,
            data=data.data
        )
        
        self.db.add(section)
        self.db.flush()
        
        return section

    def update_section(
        self,
        section_id: uuid.UUID,
        data: PageSectionUpdate
    ) -> PageSection:
        """
        Update a section.
        
        Args:
            section_id: ID of section to update
            data: Section update data
        
        Returns:
            Updated PageSection object
        """
        section = self.db.scalar(select(PageSection).where(PageSection.id == section_id))
        if not section:
            raise ValueError(f"Section with ID {section_id} not found")
        
        if data.section_type is not None:
            section.section_type = data.section_type
        
        if data.order is not None:
            section.order = data.order
        
        if data.data is not None:
            section.data = data.data
        
        self.db.flush()
        
        return section

    def delete_section(self, section_id: uuid.UUID) -> bool:
        """
        Delete a section.
        
        Args:
            section_id: ID of section to delete
        
        Returns:
            True if deleted, False if not found
        """
        section = self.db.scalar(select(PageSection).where(PageSection.id == section_id))
        if not section:
            return False
        
        self.db.delete(section)
        return True

    def reorder_sections(
        self,
        page_id: uuid.UUID,
        section_orders: dict[uuid.UUID, int]
    ) -> list[PageSection]:
        """
        Reorder sections on a page.
        
        Args:
            page_id: ID of page
            section_orders: Map of section_id to new order
        
        Returns:
            List of updated sections
        """
        sections = self.db.scalars(
            select(PageSection).where(PageSection.page_id == page_id)
        ).all()
        
        for section in sections:
            if section.id in section_orders:
                section.order = section_orders[section.id]
        
        self.db.flush()
        
        return sections

    # ========================================================================
    # IMAGE OPERATIONS
    # ========================================================================

    def create_image(
        self,
        data: CMSImageCreate,
        file_path: str,
        mime_type: str,
        file_size: Optional[int],
        user_id: uuid.UUID
    ) -> CMSImage:
        """
        Create a CMS image record.
        
        Args:
            data: Image metadata
            file_path: S3 key or local file path
            mime_type: MIME type of the image
            file_size: File size in bytes
            user_id: ID of user uploading the image
        
        Returns:
            Created CMSImage object
        """
        image = CMSImage(
            filename=data.filename,
            file_path=file_path,
            mime_type=mime_type,
            file_size=file_size,
            alt_text=data.alt_text,
            uploaded_by_id=user_id,
            used_in_pages={"page_ids": []},
            is_active=True
        )
        
        self.db.add(image)
        self.db.flush()
        
        return image

    def get_image(self, image_id: uuid.UUID) -> Optional[CMSImage]:
        """Get an image by ID."""
        return self.db.scalar(select(CMSImage).where(CMSImage.id == image_id))

    def list_images(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True
    ) -> tuple[list[CMSImage], int]:
        """
        List all CMS images.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: If True, only return active images
        
        Returns:
            Tuple of (images list, total count)
        """
        query = select(CMSImage)
        count_query = select(func.count(CMSImage.id))
        
        if active_only:
            query = query.where(CMSImage.is_active == True)
            count_query = count_query.where(CMSImage.is_active == True)
        
        # Get total count
        total = self.db.scalar(count_query)
        
        # Apply pagination
        query = query.order_by(CMSImage.created_at.desc()).offset(skip).limit(limit)
        
        images = self.db.scalars(query).all()
        return images, total

    def update_image(
        self,
        image_id: uuid.UUID,
        data: CMSImageUpdate
    ) -> CMSImage:
        """
        Update image metadata.
        
        Args:
            image_id: ID of image to update
            data: Update data
        
        Returns:
            Updated CMSImage object
        """
        image = self.get_image(image_id)
        if not image:
            raise ValueError(f"Image with ID {image_id} not found")
        
        if data.alt_text is not None:
            image.alt_text = data.alt_text
        
        self.db.flush()
        
        return image

    def delete_image(self, image_id: uuid.UUID) -> bool:
        """
        Soft delete an image by marking it inactive.
        
        Args:
            image_id: ID of image to delete
        
        Returns:
            True if deleted, False if not found
        """
        image = self.get_image(image_id)
        if not image:
            return False
        
        image.is_active = False
        self.db.flush()
        
        return True

    def update_image_usage(
        self,
        image_id: uuid.UUID,
        page_id: uuid.UUID,
        add: bool = True
    ) -> CMSImage:
        """
        Update page usage tracking for an image.
        
        Args:
            image_id: ID of image
            page_id: ID of page using the image
            add: If True, add usage; if False, remove usage
        
        Returns:
            Updated CMSImage object
        """
        image = self.get_image(image_id)
        if not image:
            raise ValueError(f"Image with ID {image_id} not found")
        
        if not image.used_in_pages:
            image.used_in_pages = {"page_ids": []}
        
        page_ids = image.used_in_pages.get("page_ids", [])
        
        if add:
            if str(page_id) not in page_ids:
                page_ids.append(str(page_id))
        else:
            if str(page_id) in page_ids:
                page_ids.remove(str(page_id))
        
        image.used_in_pages = {"page_ids": page_ids}
        self.db.flush()
        
        return image
