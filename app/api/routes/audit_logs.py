"""API endpoints for audit log management."""
from datetime import timezone
from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.audit_log import (
    AuditLogResponse,
    AuditLogListResponse,
    AuditLogFilter,
    AuditLogSummary,
    AuditLogFilterOptionsResponse,
    UserActivitySummary,
    EntityActivitySummary,
    RecentChangesResponse,
    AuditTrailResponse,
    BulkAuditLogCreate,
    BulkAuditLogResponse,
)
from app.services.audit_log import (
    get_audit_logs,
    get_audit_log_by_id,
    get_audit_summary,
    get_user_activity_summary,
    get_entity_activity_summary,
    get_recent_changes,
    get_entity_audit_trail,
    create_bulk_audit_logs,
)

router = APIRouter(prefix="/admin/audit-logs", tags=["audit-logs"])


@router.get(
    "/filter-options",
    response_model=AuditLogFilterOptionsResponse,
    summary="Get Audit Log Filter Options",
    description="Get available options for audit log filters (actions, roles, entities).",
)
def get_audit_log_filter_options(
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditLogFilterOptionsResponse:
    """Get available filter options for audit logs."""
    
    # Get available actions grouped by category
    from app.models.audit_log import AuditAction
    
    action_categories = {
        "Authentication": [
            {"value": action.value, "label": action.value.replace("auth_", "").replace("_", " ").title()}
            for action in AuditAction if action.value.startswith("auth_")
        ],
        "User Management": [
            {"value": action.value, "label": action.value.replace("user_", "").replace("_", " ").title()}
            for action in AuditAction if action.value.startswith("user_")
        ],
        "Checklist": [
            {"value": action.value, "label": action.value.replace("checklist_", "").replace("_", " ").title()}
            for action in AuditAction if action.value.startswith("checklist_")
        ],
        "Assessment": [
            {"value": action.value, "label": action.value.replace("assessment_", "").replace("_", " ").title()}
            for action in AuditAction if action.value.startswith("assessment_")
        ],
        "Review": [
            {"value": action.value, "label": action.value.replace("assessment_review_", "").replace("answer_review_", "").replace("_", " ").title()}
            for action in AuditAction if "review" in action.value
        ],
        "Report": [
            {"value": action.value, "label": action.value.replace("report_", "").replace("_", " ").title()}
            for action in AuditAction if action.value.startswith("report_")
        ]
    }
    
    # Get available actor roles
    actor_roles = [
        {"value": "admin", "label": "Admin"},
        {"value": "auditor", "label": "Auditor"},
        {"value": "customer", "label": "Customer"}
    ]
    
    # Get available target entities
    target_entities = [
        {"value": "auth", "label": "Authentication"},
        {"value": "user", "label": "User"},
        {"value": "checklist", "label": "Checklist"},
        {"value": "assessment", "label": "Assessment"},
        {"value": "assessment_review", "label": "Assessment Review"},
        {"value": "report", "label": "Report"},
        {"value": "payment", "label": "Payment"},
        {"value": "media", "label": "Media"},
        {"value": "system", "label": "System"}
    ]
    
    return {
        "actions": action_categories,
        "actor_roles": actor_roles,
        "target_entities": target_entities
    }


@router.get(
    "/",
    response_model=AuditLogListResponse,
    summary="Get Audit Logs",
    description="Get audit logs with filtering and pagination.",
)
def get_audit_logs_endpoint(
    request: Request,
    actor_user_id: Optional[UUID] = Query(None, description="Filter by actor user ID"),
    actor_role: Optional[str] = Query(None, description="Filter by actor role"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    target_entity: Optional[str] = Query(None, description="Filter by target entity type"),
    target_id: Optional[UUID] = Query(None, description="Filter by target ID"),
    target_user_id: Optional[UUID] = Query(None, description="Filter by affected user ID"),
    success: Optional[bool] = Query(None, description="Filter by success status"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    date_from: Optional[str] = Query(None, description="Filter by date from (ISO format)"),
    date_to: Optional[str] = Query(None, description="Filter by date to (ISO format)"),
    search: Optional[str] = Query(None, description="Search in changes summary"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    order_by: str = Query("created_at", description="Field to sort by"),
    order_direction: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """Get audit logs with filtering."""
    
    # Parse date filters
    from datetime import datetime
    
    parsed_date_from = None
    parsed_date_to = None
    
    if date_from:
        try:
            parsed_date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format. Use ISO format.")
    
    if date_to:
        try:
            parsed_date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format. Use ISO format.")
    
    filters = AuditLogFilter(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        target_entity=target_entity,
        target_id=target_id,
        target_user_id=target_user_id,
        success=success,
        ip_address=ip_address,
        session_id=session_id,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        search=search,
    )
    
    return get_audit_logs(
        db=db,
        filters=filters,
        skip=skip,
        limit=limit,
        order_by=order_by,
        order_direction=order_direction
    )


@router.get(
    "/{log_id}",
    response_model=AuditLogResponse,
    summary="Get Audit Log by ID",
    description="Get a specific audit log entry by ID.",
)
def get_audit_log_endpoint(
    log_id: UUID,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditLogResponse:
    """Get a specific audit log entry."""
    
    log = get_audit_log_by_id(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    
    return log


@router.get(
    "/summary/dashboard",
    response_model=AuditLogSummary,
    summary="Get Audit Summary Dashboard",
    description="Get comprehensive audit summary statistics for dashboard.",
)
def get_audit_summary_endpoint(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include in summary"),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditLogSummary:
    """Get audit summary statistics."""
    
    return get_audit_summary(db, days=days)


@router.get(
    "/recent-changes",
    response_model=RecentChangesResponse,
    summary="Get Recent Changes",
    description="Get recent changes across all entities.",
)
def get_recent_changes_endpoint(
    request: Request,
    time_period: str = Query("last_24_hours", pattern="^(last_24_hours|last_7_days|last_30_days)$", description="Time period for changes"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of changes to return"),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> RecentChangesResponse:
    """Get recent changes."""
    
    return get_recent_changes(db, time_period=time_period, limit=limit)


@router.get(
    "/users/{user_id}/activity",
    response_model=UserActivitySummary,
    summary="Get User Activity Summary",
    description="Get activity summary for a specific user.",
)
def get_user_activity_endpoint(
    user_id: UUID,
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> UserActivitySummary:
    """Get user activity summary."""
    
    activity = get_user_activity_summary(db, user_id, days=days)
    if not activity:
        raise HTTPException(status_code=404, detail="User not found or no activity")
    
    return activity


@router.get(
    "/entities/{entity_type}/{entity_id}/activity",
    response_model=EntityActivitySummary,
    summary="Get Entity Activity Summary",
    description="Get activity summary for a specific entity.",
)
def get_entity_activity_endpoint(
    entity_type: str,
    entity_id: UUID,
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> EntityActivitySummary:
    """Get entity activity summary."""
    
    return get_entity_activity_summary(db, entity_type, entity_id, days=days)


@router.get(
    "/entities/{entity_type}/{entity_id}/trail",
    response_model=AuditTrailResponse,
    summary="Get Entity Audit Trail",
    description="Get complete audit trail for a specific entity.",
)
def get_entity_audit_trail_endpoint(
    entity_type: str,
    entity_id: UUID,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditTrailResponse:
    """Get complete audit trail for an entity."""
    
    return get_entity_audit_trail(db, entity_type, entity_id)


@router.post(
    "/bulk-create",
    response_model=BulkAuditLogResponse,
    summary="Create Bulk Audit Logs",
    description="Create multiple audit log entries at once.",
)
def create_bulk_audit_logs_endpoint(
    bulk_data: BulkAuditLogCreate,
    request: Request,
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> BulkAuditLogResponse:
    """Create bulk audit logs."""
    
    return create_bulk_audit_logs(db, bulk_data)


# Quick access endpoints for common audit scenarios

@router.get(
    "/login-activity",
    response_model=AuditLogListResponse,
    summary="Get Login Activity",
    description="Get recent login and logout activity.",
)
def get_login_activity_endpoint(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look back"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """Get login activity."""
    
    from datetime import datetime, timedelta
    from app.schemas.audit_log import AuditLogFilter
    
    date_from = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    filters = AuditLogFilter(
        action="auth_login",
        date_from=date_from,
    )
    
    return get_audit_logs(db, filters=filters, skip=skip, limit=limit)


@router.get(
    "/failed-actions",
    response_model=AuditLogListResponse,
    summary="Get Failed Actions",
    description="Get recent failed actions and errors.",
)
def get_failed_actions_endpoint(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look back"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """Get failed actions."""
    
    from datetime import datetime, timedelta
    from app.schemas.audit_log import AuditLogFilter
    
    date_from = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    filters = AuditLogFilter(
        success=False,
        date_from=date_from,
    )
    
    return get_audit_logs(db, filters=filters, skip=skip, limit=limit)


@router.get(
    "/user-changes",
    response_model=AuditLogListResponse,
    summary="Get User Management Changes",
    description="Get recent user management actions (create, update, role changes).",
)
def get_user_changes_endpoint(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look back"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """Get user management changes."""
    
    from datetime import datetime, timedelta
    from app.schemas.audit_log import AuditLogFilter
    
    date_from = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    filters = AuditLogFilter(
        target_entity="user",
        date_from=date_from,
    )
    
    return get_audit_logs(db, filters=filters, skip=skip, limit=limit)


@router.get(
    "/assessment-activity",
    response_model=AuditLogListResponse,
    summary="Get Assessment Activity",
    description="Get recent assessment-related activity.",
)
def get_assessment_activity_endpoint(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look back"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """Get assessment activity."""
    
    from datetime import datetime, timedelta
    from app.schemas.audit_log import AuditLogFilter
    
    date_from = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    filters = AuditLogFilter(
        target_entity="assessment",
        date_from=date_from,
    )
    
    return get_audit_logs(db, filters=filters, skip=skip, limit=limit)


@router.get(
    "/review-activity",
    response_model=AuditLogListResponse,
    summary="Get Review Activity",
    description="Get recent assessment review activity.",
)
def get_review_activity_endpoint(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look back"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """Get review activity."""
    
    from datetime import datetime, timedelta
    from app.schemas.audit_log import AuditLogFilter
    
    date_from = datetime.now(timezone.utc) - timedelta(hours=hours)

    filters = AuditLogFilter(date_from=date_from)
    response = get_audit_logs(db, filters=filters, skip=0, limit=200)
    review_logs = [
        log for log in response.logs
        if log.target_entity in {"assessment_review", "report"}
    ]

    total = len(review_logs)
    paged_logs = review_logs[skip: skip + limit]
    pages = (total + limit - 1) // limit if limit > 0 else 0
    page = (skip // limit) + 1 if limit > 0 else 1

    return AuditLogListResponse(
        logs=paged_logs,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        filters_applied={"date_from": date_from.isoformat(), "target_entities": ["assessment_review", "report"]},
        generated_at=response.generated_at,
    )


@router.get(
    "/system-actions",
    response_model=AuditLogListResponse,
    summary="Get System Actions",
    description="Get recent system-level actions (backup, maintenance, etc.).",
)
def get_system_actions_endpoint(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look back"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """Get system actions."""
    
    from datetime import datetime, timedelta
    from app.schemas.audit_log import AuditLogFilter
    
    date_from = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    filters = AuditLogFilter(
        target_entity="system",
        date_from=date_from,
    )
    
    return get_audit_logs(db, filters=filters, skip=skip, limit=limit)


# Statistics and analytics endpoints

@router.get(
    "/stats/actions-by-hour",
    summary="Get Actions by Hour",
    description="Get action statistics grouped by hour of day.",
)
def get_actions_by_hour_endpoint(
    request: Request,
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get actions by hour statistics."""
    
    from datetime import datetime, timedelta
    from sqlalchemy import extract
    
    date_from = datetime.now(timezone.utc) - timedelta(days=days)
    
    result = (
        db.query(
            extract('hour', AuditLog.created_at).label('hour'),
            func.count(AuditLog.id).label('count')
        )
        .filter(AuditLog.created_at >= date_from)
        .group_by(extract('hour', AuditLog.created_at))
        .order_by('hour')
        .all()
    )
    
    return [{"hour": int(hour), "count": count} for hour, count in result]


@router.get(
    "/stats/actions-by-entity",
    summary="Get Actions by Entity",
    description="Get action statistics grouped by entity type.",
)
def get_actions_by_entity_endpoint(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get actions by entity statistics."""
    
    from datetime import datetime, timedelta
    
    date_from = datetime.now(timezone.utc) - timedelta(days=days)
    
    result = (
        db.query(
            AuditLog.target_entity,
            func.count(AuditLog.id).label('count')
        )
        .filter(AuditLog.created_at >= date_from)
        .group_by(AuditLog.target_entity)
        .order_by(desc('count'))
        .all()
    )
    
    return [{"entity": entity, "count": count} for entity, count in result]


@router.get(
    "/stats/top-users",
    summary="Get Top Active Users",
    description="Get users with the most activity.",
)
def get_top_users_endpoint(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    limit: int = Query(10, ge=1, le=50, description="Number of users to return"),
    admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get top active users."""
    
    from datetime import datetime, timedelta
    
    date_from = datetime.now(timezone.utc) - timedelta(days=days)
    
    result = (
        db.query(
            AuditLog.actor_user_id,
            func.count(AuditLog.id).label('count')
        )
        .filter(
            and_(
                AuditLog.created_at >= date_from,
                AuditLog.actor_user_id.is_not(None)
            )
        )
        .group_by(AuditLog.actor_user_id)
        .order_by(desc('count'))
        .limit(limit)
        .all()
    )
    
    # Get user details
    user_ids = [user_id for user_id, _ in result]
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    user_lookup = {user.id: user for user in users}
    
    top_users = []
    for user_id, count in result:
        user = user_lookup.get(user_id)
        if user:
            top_users.append({
                "user_id": user_id,
                "user_name": user.email,
                "user_email": user.email,
                "user_role": user.role.value if user.role else "unknown",
                "count": count
            })
    
    return top_users
