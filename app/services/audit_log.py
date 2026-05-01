"""Service layer for audit log operations."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import func, select, and_, or_, desc, asc, String
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.audit_log import AuditLog, AuditAction
from app.models.user import User
from app.schemas.audit_log import (
    AuditLogCreate,
    AuditLogUpdate,
    AuditLogResponse,
    AuditLogFilter,
    AuditLogListResponse,
    AuditLogSummary,
    UserActivitySummary,
    EntityActivitySummary,
    RecentChangesResponse,
    AuditTrailResponse,
    AuditAnalytics,
    UserActivitySummary,
    BulkAuditLogCreate,
    BulkAuditLogResponse,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_audit_log(
    db: Session,
    action: str,
    target_entity: str,
    actor_user_id: Optional[UUID] = None,
    target_id: Optional[UUID] = None,
    target_user_id: Optional[UUID] = None,
    before_json: Optional[Dict[str, Any]] = None,
    after_json: Optional[Dict[str, Any]] = None,
    changes_summary: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
) -> AuditLog:
    """Create a new audit log entry."""
    
    # Get actor role if user_id provided
    actor_role = None
    if actor_user_id:
        user = db.query(User).filter(User.id == actor_user_id).first()
        if user:
            actor_role = user.role.value if user.role else None
    
    audit_log = AuditLog(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        target_entity=target_entity,
        target_id=target_id,
        target_user_id=target_user_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id,
        before_json=before_json,
        after_json=after_json,
        changes_summary=changes_summary,
        success=success,
        error_message=error_message,
        metadata=metadata,
    )
    
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    
    return audit_log


def get_audit_logs(
    db: Session,
    filters: Optional[AuditLogFilter] = None,
    skip: int = 0,
    limit: int = 50,
    order_by: str = "created_at",
    order_direction: str = "desc"
) -> AuditLogListResponse:
    """Get audit logs with filtering and pagination."""
    
    query = db.query(AuditLog)
    
    # Apply filters
    if filters:
        if filters.actor_user_id:
            query = query.filter(AuditLog.actor_user_id == filters.actor_user_id)
        
        if filters.actor_role:
            query = query.filter(AuditLog.actor_role == filters.actor_role)
        
        if filters.action:
            # Check if the action is a valid enum value
            if filters.action in [action.value for action in AuditAction]:
                query = query.filter(AuditLog.action == filters.action)
            else:
                # Invalid enum value, return empty result set by using a condition that's always false
                query = query.filter(AuditLog.action != AuditLog.action)  # This will always be false, returning no rows
        
        if filters.target_entity:
            query = query.filter(AuditLog.target_entity == filters.target_entity)
        
        if filters.target_id:
            query = query.filter(AuditLog.target_id == filters.target_id)
        
        if filters.target_user_id:
            query = query.filter(AuditLog.target_user_id == filters.target_user_id)
        
        if filters.success is not None:
            query = query.filter(AuditLog.success == filters.success)
        
        if filters.ip_address:
            query = query.filter(AuditLog.ip_address == filters.ip_address)
        
        if filters.session_id:
            query = query.filter(AuditLog.session_id == filters.session_id)
        
        if filters.date_from:
            query = query.filter(AuditLog.created_at >= filters.date_from)
        
        if filters.date_to:
            query = query.filter(AuditLog.created_at <= filters.date_to)
        
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    AuditLog.changes_summary.ilike(search_term),
                    AuditLog.target_entity.ilike(search_term),
                    AuditLog.action.cast(String).ilike(search_term),
                    AuditLog.error_message.ilike(search_term),
                )
            )
    
    # Count total
    total = query.count()
    
    # Apply ordering
    order_column = getattr(AuditLog, order_by, AuditLog.created_at)
    if order_direction.lower() == "desc":
        query = query.order_by(desc(order_column))
    else:
        query = query.order_by(asc(order_column))
    
    # Apply pagination
    logs = query.offset(skip).limit(limit).all()
    
    # Get user information for actors and targets
    actor_user_ids = {log.actor_user_id for log in logs if log.actor_user_id}
    target_user_ids = {log.target_user_id for log in logs if log.target_user_id}
    
    users = db.query(User).filter(
        or_(
            User.id.in_(actor_user_ids),
            User.id.in_(target_user_ids)
        )
    ).all()
    
    user_lookup = {user.id: user for user in users}
    
    # Build response
    log_responses = []
    for log in logs:
        actor_user = user_lookup.get(log.actor_user_id) if log.actor_user_id else None
        target_user = user_lookup.get(log.target_user_id) if log.target_user_id else None
        
        log_response = AuditLogResponse.from_orm(log)
        log_response.actor_name = actor_user.email if actor_user else None
        log_response.actor_email = actor_user.email if actor_user else None
        log_response.target_user_name = target_user.email if target_user else None
        log_response.target_user_email = target_user.email if target_user else None
        
        log_responses.append(log_response)
    
    # Calculate pagination info
    pages = (total + limit - 1) // limit if limit > 0 else 0
    page = (skip // limit) + 1 if limit > 0 else 1
    
    return AuditLogListResponse(
        logs=log_responses,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        filters_applied=filters.dict(exclude_unset=True) if filters else None,
        generated_at=_now_utc()
    )


def get_audit_log_by_id(
    db: Session,
    log_id: UUID
) -> Optional[AuditLogResponse]:
    """Get a specific audit log by ID."""
    
    log = db.query(AuditLog).filter(AuditLog.id == log_id).first()
    if not log:
        return None
    
    # Get user information
    actor_user = None
    target_user = None
    
    if log.actor_user_id:
        actor_user = db.query(User).filter(User.id == log.actor_user_id).first()
    
    if log.target_user_id:
        target_user = db.query(User).filter(User.id == log.target_user_id).first()
    
    # Build response
    log_response = AuditLogResponse.from_orm(log)
    log_response.actor_name = actor_user.email if actor_user else None
    log_response.actor_email = actor_user.email if actor_user else None
    log_response.target_user_name = target_user.email if target_user else None
    log_response.target_user_email = target_user.email if target_user else None
    
    return log_response


def get_audit_summary(
    db: Session,
    days: int = 30
) -> AuditLogSummary:
    """Get audit log summary statistics."""
    
    date_from = _now_utc() - timedelta(days=days)
    
    # Basic counts
    total_logs = (
        db.scalar(
            select(func.count(AuditLog.id))
            .filter(AuditLog.created_at >= date_from)
        ) or 0
    )
    
    successful_actions = (
        db.scalar(
            select(func.count(AuditLog.id))
            .filter(
                and_(
                    AuditLog.created_at >= date_from,
                    AuditLog.success == True
                )
            )
        ) or 0
    )
    
    failed_actions = (
        db.scalar(
            select(func.count(AuditLog.id))
            .filter(
                and_(
                    AuditLog.created_at >= date_from,
                    AuditLog.success == False
                )
            )
        ) or 0
    )
    
    # Unique users
    unique_users = (
        db.scalar(
            select(func.count(func.distinct(AuditLog.actor_user_id)))
            .filter(
                and_(
                    AuditLog.created_at >= date_from,
                    AuditLog.actor_user_id.is_not(None)
                )
            )
        ) or 0
    )
    
    # Unique actions
    unique_actions = (
        db.scalar(
            select(func.count(func.distinct(AuditLog.action)))
            .filter(AuditLog.created_at >= date_from)
        ) or 0
    )
    
    # Most common actions
    most_common_actions = (
        db.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        )
        .filter(AuditLog.created_at >= date_from)
        .group_by(AuditLog.action)
        .order_by(desc('count'))
        .limit(10)
        .all()
    )
    
    most_common_actions = [
        {"action": action, "count": count} 
        for action, count in most_common_actions
    ]
    
    # Recent activity
    recent_logs = (
        db.query(AuditLog)
        .filter(AuditLog.created_at >= date_from)
        .order_by(desc(AuditLog.created_at))
        .limit(10)
        .all()
    )
    
    recent_activity = []
    for log in recent_logs:
        actor_user = db.query(User).filter(User.id == log.actor_user_id).first() if log.actor_user_id else None
        
        log_response = AuditLogResponse.from_orm(log)
        log_response.actor_name = actor_user.email if actor_user else None
        log_response.actor_email = actor_user.email if actor_user else None
        
        recent_activity.append(log_response)
    
    # Activity by hour
    activity_by_hour = (
        db.query(
            func.extract('hour', AuditLog.created_at).label('hour'),
            func.count(AuditLog.id).label('count')
        )
        .filter(AuditLog.created_at >= date_from)
        .group_by(func.extract('hour', AuditLog.created_at))
        .order_by('hour')
        .all()
    )
    
    activity_by_hour = [
        {"hour": int(hour), "count": count} 
        for hour, count in activity_by_hour
    ]
    
    # Activity by entity
    activity_by_entity = (
        db.query(
            AuditLog.target_entity,
            func.count(AuditLog.id).label('count')
        )
        .filter(AuditLog.created_at >= date_from)
        .group_by(AuditLog.target_entity)
        .order_by(desc('count'))
        .limit(10)
        .all()
    )
    
    activity_by_entity = [
        {"entity": entity, "count": count} 
        for entity, count in activity_by_entity
    ]
    
    # Top users
    top_users = (
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
        .limit(10)
        .all()
    )
    
    top_users_result = []
    for user_id, count in top_users:
        user = db.query(User).filter(User.id == user_id).first()
        top_users_result.append({
            "user_id": user_id,
            "user_name": user.email if user else "Unknown",
            "user_email": user.email if user else "unknown@example.com",
            "count": count
        })
    
    return AuditLogSummary(
        total_logs=total_logs,
        successful_actions=successful_actions,
        failed_actions=failed_actions,
        unique_users=unique_users,
        unique_actions=unique_actions,
        most_common_actions=most_common_actions,
        recent_activity=recent_activity,
        activity_by_hour=activity_by_hour,
        activity_by_entity=activity_by_entity,
        top_users=top_users_result,
        generated_at=_now_utc()
    )


def get_user_activity_summary(
    db: Session,
    user_id: UUID,
    days: int = 30
) -> Optional[UserActivitySummary]:
    """Get activity summary for a specific user."""
    
    date_from = _now_utc() - timedelta(days=days)
    
    # Get user info
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    
    # Total actions
    total_actions = (
        db.scalar(
            select(func.count(AuditLog.id))
            .filter(
                and_(
                    AuditLog.actor_user_id == user_id,
                    AuditLog.created_at >= date_from
                )
            )
        ) or 0
    )
    
    # Successful actions
    successful_actions = (
        db.scalar(
            select(func.count(AuditLog.id))
            .filter(
                and_(
                    AuditLog.actor_user_id == user_id,
                    AuditLog.created_at >= date_from,
                    AuditLog.success == True
                )
            )
        ) or 0
    )
    
    # Failed actions
    failed_actions = total_actions - successful_actions
    
    # Last activity
    last_activity = (
        db.query(AuditLog.created_at)
        .filter(AuditLog.actor_user_id == user_id)
        .order_by(desc(AuditLog.created_at))
        .first()
    )
    
    last_activity = last_activity[0] if last_activity else None
    
    # Most common actions
    most_common_actions = (
        db.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        )
        .filter(
            and_(
                AuditLog.actor_user_id == user_id,
                AuditLog.created_at >= date_from
            )
        )
        .group_by(AuditLog.action)
        .order_by(desc('count'))
        .limit(10)
        .all()
    )
    
    most_common_actions = [
        {"action": action, "count": count} 
        for action, count in most_common_actions
    ]
    
    # Entities affected
    entities_affected = (
        db.query(func.distinct(AuditLog.target_entity))
        .filter(
            and_(
                AuditLog.actor_user_id == user_id,
                AuditLog.created_at >= date_from
            )
        )
        .all()
    )
    
    entities_affected = [entity[0] for entity in entities_affected]
    
    # Activity timeline (last 7 days)
    timeline_date_from = _now_utc() - timedelta(days=7)
    activity_timeline = (
        db.query(
            func.date(AuditLog.created_at).label('date'),
            func.count(AuditLog.id).label('count')
        )
        .filter(
            and_(
                AuditLog.actor_user_id == user_id,
                AuditLog.created_at >= timeline_date_from
            )
        )
        .group_by(func.date(AuditLog.created_at))
        .order_by('date')
        .all()
    )
    
    activity_timeline = [
        {"date": str(date), "count": count} 
        for date, count in activity_timeline
    ]
    
    return UserActivitySummary(
        user_id=user_id,
        user_name=user.email,
        user_email=user.email,
        user_role=user.role.value if user.role else "unknown",
        total_actions=total_actions,
        successful_actions=successful_actions,
        failed_actions=failed_actions,
        last_activity=last_activity,
        most_common_actions=most_common_actions,
        entities_affected=entities_affected,
        activity_timeline=activity_timeline
    )


def get_entity_activity_summary(
    db: Session,
    entity_type: str,
    entity_id: UUID,
    days: int = 30
) -> EntityActivitySummary:
    """Get activity summary for a specific entity."""
    
    date_from = _now_utc() - timedelta(days=days)
    
    # Total changes
    total_changes = (
        db.scalar(
            select(func.count(AuditLog.id))
            .filter(
                and_(
                    AuditLog.target_entity == entity_type,
                    AuditLog.target_id == entity_id,
                    AuditLog.created_at >= date_from
                )
            )
        ) or 0
    )
    
    # Last change
    last_change = (
        db.query(AuditLog.created_at)
        .filter(
            and_(
                AuditLog.target_entity == entity_type,
                AuditLog.target_id == entity_id
            )
        )
        .order_by(desc(AuditLog.created_at))
        .first()
    )
    
    last_change = last_change[0] if last_change else None
    
    # Changed by users
    changed_by_users = (
        db.query(
            AuditLog.actor_user_id,
            func.count(AuditLog.id).label('count')
        )
        .filter(
            and_(
                AuditLog.target_entity == entity_type,
                AuditLog.target_id == entity_id,
                AuditLog.created_at >= date_from
            )
        )
        .group_by(AuditLog.actor_user_id)
        .order_by(desc('count'))
        .all()
    )
    
    changed_by_users_result = []
    for user_id, count in changed_by_users:
        user = db.query(User).filter(User.id == user_id).first()
        changed_by_users_result.append({
            "user_id": user_id,
            "user_name": user.email if user else "Unknown",
            "user_email": user.email if user else "unknown@example.com",
            "count": count
        })
    
    # Change types
    change_types = (
        db.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        )
        .filter(
            and_(
                AuditLog.target_entity == entity_type,
                AuditLog.target_id == entity_id,
                AuditLog.created_at >= date_from
            )
        )
        .group_by(AuditLog.action)
        .order_by(desc('count'))
        .all()
    )
    
    change_types = [
        {"action": action, "count": count} 
        for action, count in change_types
    ]
    
    # Recent changes
    recent_changes = (
        db.query(AuditLog)
        .filter(
            and_(
                AuditLog.target_entity == entity_type,
                AuditLog.target_id == entity_id
            )
        )
        .order_by(desc(AuditLog.created_at))
        .limit(10)
        .all()
    )
    
    recent_changes_responses = []
    for change in recent_changes:
        actor_user = db.query(User).filter(User.id == change.actor_user_id).first() if change.actor_user_id else None
        
        change_response = AuditLogResponse.from_orm(change)
        change_response.actor_name = actor_user.full_name if actor_user else None
        change_response.actor_email = actor_user.email if actor_user else None
        
        recent_changes_responses.append(change_response)
    
    return EntityActivitySummary(
        entity_type=entity_type,
        entity_id=entity_id,
        total_changes=total_changes,
        last_changed=last_change,
        changed_by_users=changed_by_users_result,
        change_types=change_types,
        recent_changes=recent_changes_responses
    )


def get_recent_changes(
    db: Session,
    time_period: str = "last_24_hours",
    limit: int = 50
) -> RecentChangesResponse:
    """Get recent changes based on time period."""
    
    # Calculate date range
    if time_period == "last_24_hours":
        date_from = _now_utc() - timedelta(hours=24)
    elif time_period == "last_7_days":
        date_from = _now_utc() - timedelta(days=7)
    elif time_period == "last_30_days":
        date_from = _now_utc() - timedelta(days=30)
    else:
        date_from = _now_utc() - timedelta(hours=24)  # Default to 24 hours
    
    # Get recent changes
    recent_logs = (
        db.query(AuditLog)
        .filter(AuditLog.created_at >= date_from)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .all()
    )
    
    # Get user information
    user_ids = {log.actor_user_id for log in recent_logs if log.actor_user_id}
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    user_lookup = {user.id: user for user in users}
    
    # Build response
    changes = []
    for log in recent_logs:
        actor_user = user_lookup.get(log.actor_user_id) if log.actor_user_id else None
        
        log_response = AuditLogResponse.from_orm(log)
        log_response.actor_name = actor_user.email if actor_user else None
        log_response.actor_email = actor_user.email if actor_user else None
        
        changes.append(log_response)
    
    total = (
        db.scalar(
            select(func.count(AuditLog.id))
            .filter(AuditLog.created_at >= date_from)
        ) or 0
    )
    
    return RecentChangesResponse(
        changes=changes,
        total=total,
        time_period=time_period,
        generated_at=_now_utc()
    )


def get_entity_audit_trail(
    db: Session,
    entity_type: str,
    entity_id: UUID
) -> AuditTrailResponse:
    """Get complete audit trail for an entity."""
    
    # Get all logs for this entity
    logs = (
        db.query(AuditLog)
        .filter(
            and_(
                AuditLog.target_entity == entity_type,
                AuditLog.target_id == entity_id
            )
        )
        .order_by(desc(AuditLog.created_at))
        .all()
    )
    
    if not logs:
        return AuditTrailResponse(
            entity_type=entity_type,
            entity_id=entity_id,
            trail=[],
            total_changes=0,
            first_change=None,
            last_change=None,
            users_involved=[],
            change_summary={}
        )
    
    # Get user information
    user_ids = {log.actor_user_id for log in logs if log.actor_user_id}
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    user_lookup = {user.id: user for user in users}
    
    # Build trail
    trail = []
    for log in logs:
        actor_user = user_lookup.get(log.actor_user_id) if log.actor_user_id else None
        
        log_response = AuditLogResponse.from_orm(log)
        log_response.actor_name = actor_user.email if actor_user else None
        log_response.actor_email = actor_user.email if actor_user else None
        
        trail.append(log_response)
    
    # Users involved
    users_involved = []
    for user_id in user_ids:
        user = user_lookup[user_id]
        users_involved.append({
            "user_id": user_id,
            "user_name": user.email,
            "user_email": user.email,
            "user_role": user.role.value if user.role else "unknown"
        })
    
    # Change summary
    change_summary = {}
    for log in logs:
        action = log.action
        if action not in change_summary:
            change_summary[action] = 0
        change_summary[action] += 1
    
    return AuditTrailResponse(
        entity_type=entity_type,
        entity_id=entity_id,
        trail=trail,
        total_changes=len(logs),
        first_change=logs[-1].created_at if logs else None,
        last_change=logs[0].created_at if logs else None,
        users_involved=users_involved,
        change_summary=change_summary
    )


def create_bulk_audit_logs(
    db: Session,
    bulk_data: BulkAuditLogCreate
) -> BulkAuditLogResponse:
    """Create multiple audit log entries at once."""
    
    success_count = 0
    failure_count = 0
    errors = []
    
    for log_data in bulk_data.logs:
        try:
            create_audit_log(
                db=db,
                action=log_data.action,
                target_entity=log_data.target_entity,
                actor_user_id=log_data.actor_user_id,
                target_id=log_data.target_id,
                target_user_id=log_data.target_user_id,
                before_json=log_data.before_json,
                after_json=log_data.after_json,
                changes_summary=log_data.changes_summary,
                success=log_data.success,
                error_message=log_data.error_message,
                metadata=log_data.metadata,
                request_id=log_data.request_id,
                ip_address=log_data.ip_address,
                user_agent=log_data.user_agent,
                session_id=log_data.session_id,
            )
            success_count += 1
        except Exception as e:
            failure_count += 1
            errors.append({
                "log_data": log_data.dict(),
                "error": str(e)
            })
    
    return BulkAuditLogResponse(
        batch_id=bulk_data.batch_id or str(uuid4()),
        success_count=success_count,
        failure_count=failure_count,
        total_count=len(bulk_data.logs),
        errors=errors,
        created_at=_now_utc()
    )
