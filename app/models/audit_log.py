from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditAction(StrEnum):
    # Authentication actions
    auth_login = "auth_login"
    auth_logout = "auth_logout"
    auth_mfa_verify = "auth_mfa_verify"
    auth_password_change = "auth_password_change"
    auth_profile_update = "auth_profile_update"
    
    # User management actions
    user_create = "user_create"
    user_update = "user_update"
    user_delete = "user_delete"
    user_role_change = "user_role_change"
    user_status_change = "user_status_change"
    
    # Checklist actions
    checklist_create = "checklist_create"
    checklist_update = "checklist_update"
    checklist_delete = "checklist_delete"
    checklist_publish = "checklist_publish"
    checklist_archive = "checklist_archive"
    checklist_version_update = "checklist_version_update"
    
    # Assessment actions
    assessment_create = "assessment_create"
    assessment_update = "assessment_update"
    assessment_delete = "assessment_delete"
    assessment_submit = "assessment_submit"
    assessment_withdraw = "assessment_withdraw"
    assessment_extend = "assessment_extend"
    assessment_archive = "assessment_archive"
    assessment_answer_create = "assessment_answer_create"
    assessment_answer_update = "assessment_answer_update"
    assessment_answer_delete = "assessment_answer_delete"
    
    # Assessment Review actions
    assessment_review_create = "assessment_review_create"
    assessment_review_update = "assessment_review_update"
    assessment_review_submit = "assessment_review_submit"
    assessment_review_approve = "assessment_review_approve"
    assessment_review_reject = "assessment_review_reject"
    answer_review_create = "answer_review_create"
    answer_review_update = "answer_review_update"
    answer_review_delete = "answer_review_delete"
    
    # Report actions
    report_create = "report_create"
    report_update = "report_update"
    report_delete = "report_delete"
    report_approve = "report_approve"
    report_publish = "report_publish"
    report_reject = "report_reject"
    report_changes_request = "report_changes_request"
    
    # Payment actions
    payment_create = "payment_create"
    payment_update = "payment_update"
    payment_complete = "payment_complete"
    payment_refund = "payment_refund"
    payment_fail = "payment_fail"
    
    # Media/File actions
    media_upload = "media_upload"
    media_update = "media_update"
    media_delete = "media_delete"
    media_download = "media_download"
    
    # System actions
    system_backup = "system_backup"
    system_restore = "system_restore"
    system_maintenance = "system_maintenance"
    system_config_update = "system_config_update"
    
    # RBAC actions
    role_create = "role_create"
    role_update = "role_update"
    role_delete = "role_delete"
    permission_create = "permission_create"
    permission_update = "permission_update"
    permission_delete = "permission_delete"
    role_permission_assign = "role_permission_assign"
    role_permission_revoke = "role_permission_revoke"
    
    # CMS actions
    cms_page_create = "cms_page_create"
    cms_page_update = "cms_page_update"
    cms_page_delete = "cms_page_delete"
    cms_page_publish = "cms_page_publish"
    cms_section_create = "cms_section_create"
    cms_section_update = "cms_section_update"
    cms_section_delete = "cms_section_delete"
    cms_image_upload = "cms_image_upload"
    cms_image_update = "cms_image_update"
    cms_image_delete = "cms_image_delete"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", native_enum=True), nullable=False
    )
    target_entity: Mapped[str] = mapped_column(String(120), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # User affected by action
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    changes_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # Human-readable summary
    success: Mapped[bool] = mapped_column(nullable=False, default=True)  # Whether action succeeded
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)  # Error details if failed
    extra_metadata: Mapped[dict | None] = mapped_column('metadata', JSONB, nullable=True)  # Additional context
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
