"""Schemas for audit log API."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuditLogCreate(BaseModel):
    """Schema for creating audit log entries."""
    actor_user_id: Optional[UUID] = Field(None, description="User who performed the action")
    actor_role: Optional[str] = Field(None, description="Role of the actor")
    action: str = Field(..., description="Action performed")
    target_entity: str = Field(..., description="Entity type that was acted upon")
    target_id: Optional[UUID] = Field(None, description="ID of the target entity")
    target_user_id: Optional[UUID] = Field(None, description="User affected by the action")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")
    ip_address: Optional[str] = Field(None, description="IP address of the request")
    user_agent: Optional[str] = Field(None, description="User agent string")
    session_id: Optional[str] = Field(None, description="Session ID")
    before_json: Optional[Dict[str, Any]] = Field(None, description="State before change")
    after_json: Optional[Dict[str, Any]] = Field(None, description="State after change")
    changes_summary: Optional[str] = Field(None, description="Human-readable summary of changes")
    success: bool = Field(True, description="Whether the action succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata", alias="extra_metadata")


class AuditLogUpdate(BaseModel):
    """Schema for updating audit log entries (limited)."""
    changes_summary: Optional[str] = Field(None, description="Updated changes summary")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata", alias="extra_metadata")


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""
    id: UUID
    actor_user_id: Optional[UUID]
    actor_role: Optional[str]
    actor_name: Optional[str] = None  # Added from user lookup
    actor_email: Optional[str] = None  # Added from user lookup
    action: str
    target_entity: str
    target_id: Optional[UUID]
    target_user_id: Optional[UUID]
    target_user_name: Optional[str] = None  # Added from user lookup
    target_user_email: Optional[str] = None  # Added from user lookup
    request_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    session_id: Optional[str]
    before_json: Optional[Dict[str, Any]]
    after_json: Optional[Dict[str, Any]]
    changes_summary: Optional[str]
    success: bool
    error_message: Optional[str]
    metadata: Optional[Dict[str, Any]] = Field(None, alias="extra_metadata")
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogFilter(BaseModel):
    """Schema for filtering audit logs."""
    actor_user_id: Optional[UUID] = Field(None, description="Filter by actor user ID")
    actor_role: Optional[str] = Field(None, description="Filter by actor role")
    action: Optional[str] = Field(None, description="Filter by action type")
    target_entity: Optional[str] = Field(None, description="Filter by target entity type")
    target_id: Optional[UUID] = Field(None, description="Filter by target ID")
    target_user_id: Optional[UUID] = Field(None, description="Filter by affected user ID")
    success: Optional[bool] = Field(None, description="Filter by success status")
    ip_address: Optional[str] = Field(None, description="Filter by IP address")
    session_id: Optional[str] = Field(None, description="Filter by session ID")
    date_from: Optional[datetime] = Field(None, description="Filter by date from (inclusive)")
    date_to: Optional[datetime] = Field(None, description="Filter by date to (inclusive)")
    search: Optional[str] = Field(None, description="Search in changes summary")


class AuditLogListResponse(BaseModel):
    """Schema for audit log list response."""
    logs: List[AuditLogResponse]
    total: int
    page: int
    size: int
    pages: int
    filters_applied: Optional[Dict[str, Any]] = None
    generated_at: datetime


class AuditLogSummary(BaseModel):
    """Schema for audit log summary statistics."""
    total_logs: int
    successful_actions: int
    failed_actions: int
    unique_users: int
    unique_actions: int
    most_common_actions: List[Dict[str, Any]]
    recent_activity: List[AuditLogResponse]
    activity_by_hour: List[Dict[str, Any]]
    activity_by_entity: List[Dict[str, Any]]
    top_users: List[Dict[str, Any]]
    generated_at: datetime


class UserActivitySummary(BaseModel):
    """Schema for user activity summary."""
    user_id: UUID
    user_name: str
    user_email: str
    user_role: str
    total_actions: int
    successful_actions: int
    failed_actions: int
    last_activity: Optional[datetime]
    most_common_actions: List[Dict[str, Any]]
    entities_affected: List[str]
    activity_timeline: List[Dict[str, Any]]


class EntityActivitySummary(BaseModel):
    """Schema for entity activity summary."""
    entity_type: str
    entity_id: UUID
    entity_name: Optional[str] = None
    total_changes: int
    last_changed: Optional[datetime]
    changed_by_users: List[Dict[str, Any]]
    change_types: List[Dict[str, Any]]
    recent_changes: List[AuditLogResponse]


class RecentChangesResponse(BaseModel):
    """Schema for recent changes response."""
    changes: List[AuditLogResponse]
    total: int
    time_period: str  # e.g., "last_24_hours", "last_7_days", "last_30_days"
    generated_at: datetime


class AuditTrailResponse(BaseModel):
    """Schema for complete audit trail of an entity."""
    entity_type: str
    entity_id: UUID
    entity_name: Optional[str] = None
    trail: List[AuditLogResponse]
    total_changes: int
    first_change: Optional[datetime]
    last_change: Optional[datetime]
    users_involved: List[Dict[str, Any]]
    change_summary: Dict[str, Any]


class AuditAnalytics(BaseModel):
    """Schema for audit analytics."""
    time_range: str
    total_events: int
    events_per_day: List[Dict[str, Any]]
    events_per_hour: List[Dict[str, Any]]
    top_actions: List[Dict[str, Any]]
    top_entities: List[Dict[str, Any]]
    top_users: List[Dict[str, Any]]
    success_rate: float
    error_rate: float
    unique_sessions: int
    geographic_distribution: List[Dict[str, Any]]  # IP-based
    generated_at: datetime


class AuditExportRequest(BaseModel):
    """Schema for audit export request."""
    filters: Optional[AuditLogFilter] = Field(None, description="Filters to apply")
    format: str = Field("json", description="Export format: json, csv, xlsx")
    include_metadata: bool = Field(True, description="Include metadata in export")
    max_records: int = Field(10000, ge=1, le=100000, description="Maximum records to export")


class AuditExportResponse(BaseModel):
    """Schema for audit export response."""
    export_id: UUID
    status: str  # pending, processing, completed, failed
    download_url: Optional[str] = None
    file_size: Optional[int] = None
    record_count: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class BulkAuditLogCreate(BaseModel):
    """Schema for bulk audit log creation."""
    logs: List[AuditLogCreate]
    batch_id: Optional[str] = Field(None, description="Batch identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Batch metadata")


class BulkAuditLogResponse(BaseModel):
    """Schema for bulk audit log creation response."""
    batch_id: str
    success_count: int
    failure_count: int
    total_count: int
    errors: List[Dict[str, Any]]
    created_at: datetime
