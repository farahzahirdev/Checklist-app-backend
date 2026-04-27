"""Utility functions for audit logging throughout the application."""
from __future__ import annotations

from typing import Optional, Dict, Any
from uuid import UUID
import json

from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction
from app.services.audit_log import create_audit_log


class AuditLogger:
    """Centralized audit logging utility."""
    
    @staticmethod
    def log_user_action(
        db: Session,
        action: str,
        user_id: Optional[UUID] = None,
        target_user_id: Optional[UUID] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        changes_summary: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Log user-related actions."""
        
        create_audit_log(
            db=db,
            action=action,
            target_entity="user",
            target_id=target_user_id,
            actor_user_id=user_id,
            target_user_id=target_user_id,
            before_json=before_data,
            after_json=after_data,
            changes_summary=changes_summary,
            success=success,
            error_message=error_message,
            metadata=metadata,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
    
    @staticmethod
    def log_assessment_action(
        db: Session,
        action: str,
        assessment_id: UUID,
        actor_user_id: Optional[UUID] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        changes_summary: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Log assessment-related actions."""
        
        create_audit_log(
            db=db,
            action=action,
            target_entity="assessment",
            target_id=assessment_id,
            actor_user_id=actor_user_id,
            before_json=before_data,
            after_json=after_data,
            changes_summary=changes_summary,
            success=success,
            error_message=error_message,
            metadata=metadata,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
    
    @staticmethod
    def log_assessment_review_action(
        db: Session,
        action: str,
        review_id: UUID,
        actor_user_id: Optional[UUID] = None,
        target_user_id: Optional[UUID] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        changes_summary: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Log assessment review actions."""
        
        create_audit_log(
            db=db,
            action=action,
            target_entity="assessment_review",
            target_id=review_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            before_json=before_data,
            after_json=after_data,
            changes_summary=changes_summary,
            success=success,
            error_message=error_message,
            metadata=metadata,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
    
    @staticmethod
    def log_checklist_action(
        db: Session,
        action: str,
        checklist_id: UUID,
        actor_user_id: Optional[UUID] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        changes_summary: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Log checklist-related actions."""
        
        create_audit_log(
            db=db,
            action=action,
            target_entity="checklist",
            target_id=checklist_id,
            actor_user_id=actor_user_id,
            before_json=before_data,
            after_json=after_data,
            changes_summary=changes_summary,
            success=success,
            error_message=error_message,
            metadata=metadata,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
    
    @staticmethod
    def log_authentication_action(
        db: Session,
        action: str,
        user_id: UUID,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Log authentication actions."""
        
        create_audit_log(
            db=db,
            action=action,
            target_entity="auth",
            target_id=user_id,
            actor_user_id=user_id,
            target_user_id=user_id,
            success=success,
            error_message=error_message,
            metadata=metadata,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
    
    @staticmethod
    def log_system_action(
        db: Session,
        action: str,
        actor_user_id: Optional[UUID] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        changes_summary: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Log system-level actions."""
        
        create_audit_log(
            db=db,
            action=action,
            target_entity="system",
            actor_user_id=actor_user_id,
            before_json=before_data,
            after_json=after_data,
            changes_summary=changes_summary,
            success=success,
            error_message=error_message,
            metadata=metadata,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
    
    @staticmethod
    def log_payment_action(
        db: Session,
        action: str,
        payment_id: UUID,
        actor_user_id: Optional[UUID] = None,
        target_user_id: Optional[UUID] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        changes_summary: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Log payment-related actions."""
        
        create_audit_log(
            db=db,
            action=action,
            target_entity="payment",
            target_id=payment_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            before_json=before_data,
            after_json=after_data,
            changes_summary=changes_summary,
            success=success,
            error_message=error_message,
            metadata=metadata,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
    
    @staticmethod
    def log_media_action(
        db: Session,
        action: str,
        media_id: UUID,
        actor_user_id: Optional[UUID] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        changes_summary: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Log media/file actions."""
        
        create_audit_log(
            db=db,
            action=action,
            target_entity="media",
            target_id=media_id,
            actor_user_id=actor_user_id,
            before_json=before_data,
            after_json=after_data,
            changes_summary=changes_summary,
            success=success,
            error_message=error_message,
            metadata=metadata,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
    
    @staticmethod
    def log_rbac_action(
        db: Session,
        action: str,
        target_id: UUID,
        target_entity: str,
        actor_user_id: Optional[UUID] = None,
        target_user_id: Optional[UUID] = None,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        changes_summary: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Log RBAC (role/permission) actions."""
        
        create_audit_log(
            db=db,
            action=action,
            target_entity=target_entity,
            target_id=target_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            before_json=before_data,
            after_json=after_data,
            changes_summary=changes_summary,
            success=success,
            error_message=error_message,
            metadata=metadata,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
    
    @staticmethod
    def create_changes_summary(
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        action: Optional[str] = None
    ) -> str:
        """Create a human-readable summary of changes."""
        
        if not before_data and not after_data:
            return action or "No changes"
        
        changes = []
        
        if before_data and after_data:
            # Compare before and after
            for key, after_value in after_data.items():
                before_value = before_data.get(key)
                if before_value != after_value:
                    if before_value is None:
                        changes.append(f"Added {key}: {after_value}")
                    elif after_value is None:
                        changes.append(f"Removed {key}: {before_value}")
                    else:
                        changes.append(f"Changed {key}: {before_value} → {after_value}")
        elif after_data:
            # New data
            for key, value in after_data.items():
                changes.append(f"Set {key}: {value}")
        elif before_data:
            # Removed data
            for key, value in before_data.items():
                changes.append(f"Removed {key}: {value}")
        
        if changes:
            return "; ".join(changes)
        else:
            return action or "No changes detected"
    
    @staticmethod
    def extract_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from audit logs."""
        
        sensitive_fields = {
            'password', 'token', 'secret', 'key', 'credential',
            'ssn', 'social_security', 'credit_card', 'bank_account',
            'api_key', 'private_key', 'access_token', 'refresh_token'
        }
        
        def clean_dict(d: Dict[str, Any]) -> Dict[str, Any]:
            cleaned = {}
            for key, value in d.items():
                key_lower = key.lower()
                if any(field in key_lower for field in sensitive_fields):
                    cleaned[key] = "[REDACTED]"
                elif isinstance(value, dict):
                    cleaned[key] = clean_dict(value)
                elif isinstance(value, list):
                    cleaned[key] = [
                        clean_dict(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    cleaned[key] = value
            return cleaned
        
        return clean_dict(data.copy())


def get_request_info(request) -> Dict[str, Any]:
    """Extract request information for audit logging."""
    
    info = {}
    
    # IP Address
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        info["ip_address"] = forwarded_for.split(",")[0].strip()
    else:
        info["ip_address"] = request.client.host if request.client else None
    
    # User Agent
    info["user_agent"] = request.headers.get("User-Agent")
    
    # Request ID (if available)
    info["request_id"] = request.headers.get("X-Request-ID")
    
    # Session ID (if available)
    info["session_id"] = request.headers.get("X-Session-ID")
    
    return info


# Convenience decorators for automatic audit logging

def audit_action(
    action: str,
    entity_type: str,
    get_entity_id: callable = None,
    get_target_user_id: callable = None,
    log_on_failure: bool = True,
    include_request_info: bool = True
):
    """Decorator for automatic audit logging of endpoint actions."""
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would need to be implemented with proper FastAPI dependency injection
            # For now, it's a placeholder showing the concept
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator
