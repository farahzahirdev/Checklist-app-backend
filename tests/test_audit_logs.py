"""Tests for audit log functionality."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.models.audit_log import AuditLog, AuditAction
from app.models.user import User, UserRole
from app.schemas.audit_log import (
    AuditLogCreate,
    AuditLogFilter,
    AuditLogListResponse,
    AuditLogSummary,
    RecentChangesResponse,
)
from app.services.audit_log import (
    create_audit_log,
    get_audit_logs,
    get_audit_log_by_id,
    get_audit_summary,
    get_recent_changes,
    get_user_activity_summary,
    get_entity_activity_summary,
    get_entity_audit_trail,
    create_bulk_audit_logs,
)
from app.utils.audit_logger import AuditLogger


class TestAuditLogService:
    """Test audit log service functions."""
    
    def test_create_audit_log(self, db, admin_user):
        """Test creating a basic audit log entry."""
        log = create_audit_log(
            db=db,
            action=AuditAction.user_create,
            target_entity="user",
            actor_user_id=admin_user.id,
            target_id=uuid4(),
            changes_summary="Created new user account",
        )
        
        assert log is not None
        assert log.id is not None
        assert log.action == AuditAction.user_create
        assert log.target_entity == "user"
        assert log.actor_user_id == admin_user.id
        assert log.changes_summary == "Created new user account"
        assert log.success is True
    
    def test_create_audit_log_with_full_data(self, db, admin_user, customer_user):
        """Test creating audit log with all fields."""
        target_id = uuid4()
        
        log = create_audit_log(
            db=db,
            action=AuditAction.assessment_review_create,
            target_entity="assessment_review",
            actor_user_id=admin_user.id,
            target_id=target_id,
            target_user_id=customer_user.id,
            before_json={"status": "pending"},
            after_json={"status": "in_progress"},
            changes_summary="Started assessment review",
            success=True,
            metadata={"review_type": "comprehensive"},
            request_id="req-123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            session_id="sess-456",
        )
        
        assert log.action == AuditAction.assessment_review_create
        assert log.target_entity == "assessment_review"
        assert log.target_id == target_id
        assert log.target_user_id == customer_user.id
        assert log.before_json == {"status": "pending"}
        assert log.after_json == {"status": "in_progress"}
        assert log.changes_summary == "Started assessment review"
        assert log.success is True
        assert log.metadata == {"review_type": "comprehensive"}
        assert log.request_id == "req-123"
        assert log.ip_address == "192.168.1.1"
        assert log.user_agent == "Mozilla/5.0"
        assert log.session_id == "sess-456"
    
    def test_get_audit_logs_basic(self, db, admin_user):
        """Test basic audit log retrieval."""
        # Create some test logs
        for i in range(5):
            create_audit_log(
                db=db,
                action=AuditAction.user_create,
                target_entity="user",
                actor_user_id=admin_user.id,
                target_id=uuid4(),
                changes_summary=f"Created user {i+1}",
            )
        
        # Get logs
        result = get_audit_logs(db, skip=0, limit=10)
        
        assert isinstance(result, AuditLogListResponse)
        assert len(result.logs) >= 5
        assert result.total >= 5
        assert result.page == 1
        assert result.size == 10
        assert result.pages >= 1
    
    def test_get_audit_logs_with_filters(self, db, admin_user, customer_user):
        """Test audit log retrieval with filters."""
        # Create test logs with different actions
        create_audit_log(
            db=db,
            action=AuditAction.user_create,
            target_entity="user",
            actor_user_id=admin_user.id,
            target_id=uuid4(),
            changes_summary="Admin created user",
        )
        
        create_audit_log(
            db=db,
            action=AuditAction.assessment_submit,
            target_entity="assessment",
            actor_user_id=customer_user.id,
            target_id=uuid4(),
            changes_summary="Customer submitted assessment",
        )
        
        create_audit_log(
            db=db,
            action=AuditAction.user_create,
            target_entity="user",
            actor_user_id=admin_user.id,
            target_id=uuid4(),
            changes_summary="Admin created another user",
            success=False,
            error_message="Email already exists",
        )
        
        # Filter by action
        filters = AuditLogFilter(action=AuditAction.user_create)
        result = get_audit_logs(db, filters=filters)
        
        assert len(result.logs) == 2
        assert all(log.action == AuditAction.user_create for log in result.logs)
        
        # Filter by actor
        filters = AuditLogFilter(actor_user_id=admin_user.id)
        result = get_audit_logs(db, filters=filters)
        
        assert len(result.logs) == 2
        assert all(log.actor_user_id == admin_user.id for log in result.logs)
        
        # Filter by success
        filters = AuditLogFilter(success=False)
        result = get_audit_logs(db, filters=filters)
        
        assert len(result.logs) == 1
        assert all(not log.success for log in result.logs)
    
    def test_get_audit_log_by_id(self, db, admin_user):
        """Test getting a specific audit log by ID."""
        # Create a log
        log = create_audit_log(
            db=db,
            action=AuditAction.user_create,
            target_entity="user",
            actor_user_id=admin_user.id,
            target_id=uuid4(),
            changes_summary="Test log entry",
        )
        
        # Retrieve by ID
        result = get_audit_log_by_id(db, log.id)
        
        assert result is not None
        assert result.id == log.id
        assert result.action == AuditAction.user_create
        assert result.changes_summary == "Test log entry"
        assert result.actor_name == admin_user.full_name
        assert result.actor_email == admin_user.email
    
    def test_get_audit_summary(self, db, admin_user, customer_user):
        """Test audit summary generation."""
        # Create test logs
        create_audit_log(
            db=db,
            action=AuditAction.user_create,
            target_entity="user",
            actor_user_id=admin_user.id,
            target_id=uuid4(),
            changes_summary="Created user 1",
        )
        
        create_audit_log(
            db=db,
            action=AuditAction.assessment_submit,
            target_entity="assessment",
            actor_user_id=customer_user.id,
            target_id=uuid4(),
            changes_summary="Submitted assessment",
        )
        
        create_audit_log(
            db=db,
            action=AuditAction.user_create,
            target_entity="user",
            actor_user_id=admin_user.id,
            target_id=uuid4(),
            changes_summary="Created user 2",
            success=False,
            error_message="Validation failed",
        )
        
        # Get summary
        summary = get_audit_summary(db, days=30)
        
        assert isinstance(summary, AuditLogSummary)
        assert summary.total_logs == 3
        assert summary.successful_actions == 2
        assert summary.failed_actions == 1
        assert summary.unique_users == 2
        assert summary.unique_actions == 2
        assert len(summary.most_common_actions) == 2
        assert len(summary.recent_activity) == 3
        assert len(summary.top_users) == 2
    
    def test_get_user_activity_summary(self, db, admin_user):
        """Test user activity summary."""
        # Create logs for admin user
        for i in range(5):
            create_audit_log(
                db=db,
                action=AuditAction.user_create,
                target_entity="user",
                actor_user_id=admin_user.id,
                target_id=uuid4(),
                changes_summary=f"Created user {i+1}",
                success=i < 4,  # One failure
            )
        
        # Get summary
        summary = get_user_activity_summary(db, admin_user.id, days=30)
        
        assert summary is not None
        assert summary.user_id == admin_user.id
        assert summary.user_name == admin_user.full_name or admin_user.email
        assert summary.user_email == admin_user.email
        assert summary.total_actions == 5
        assert summary.successful_actions == 4
        assert summary.failed_actions == 1
        assert len(summary.most_common_actions) == 1
        assert summary.entities_affected == ["user"]
    
    def test_get_entity_activity_summary(self, db, admin_user):
        """Test entity activity summary."""
        entity_id = uuid4()
        
        # Create logs for an entity
        for i in range(3):
            create_audit_log(
                db=db,
                action=AuditAction.assessment_update,
                target_entity="assessment",
                target_id=entity_id,
                actor_user_id=admin_user.id,
                changes_summary=f"Updated assessment {i+1}",
            )
        
        # Get summary
        summary = get_entity_activity_summary(db, "assessment", entity_id, days=30)
        
        assert summary.entity_type == "assessment"
        assert summary.entity_id == entity_id
        assert summary.total_changes == 3
        assert len(summary.changed_by_users) == 1
        assert len(summary.change_types) == 1
        assert len(summary.recent_changes) == 3
    
    def test_get_recent_changes(self, db, admin_user):
        """Test getting recent changes."""
        # Create some logs
        for i in range(10):
            create_audit_log(
                db=db,
                action=AuditAction.user_create,
                target_entity="user",
                actor_user_id=admin_user.id,
                target_id=uuid4(),
                changes_summary=f"Created user {i+1}",
            )
        
        # Get recent changes
        result = get_recent_changes(db, time_period="last_24_hours", limit=5)
        
        assert isinstance(result, RecentChangesResponse)
        assert len(result.changes) == 5
        assert result.total >= 10
        assert result.time_period == "last_24_hours"
    
    def test_get_entity_audit_trail(self, db, admin_user):
        """Test getting complete audit trail for an entity."""
        entity_id = uuid4()
        
        # Create logs for an entity
        actions = [
            AuditAction.assessment_create,
            AuditAction.assessment_update,
            AuditAction.assessment_submit,
            AuditAction.assessment_review_create,
        ]
        
        for action in actions:
            create_audit_log(
                db=db,
                action=action,
                target_entity="assessment",
                target_id=entity_id,
                actor_user_id=admin_user.id,
                changes_summary=f"Action: {action}",
            )
        
        # Get audit trail
        trail = get_entity_audit_trail(db, "assessment", entity_id)
        
        assert trail.entity_type == "assessment"
        assert trail.entity_id == entity_id
        assert trail.total_changes == 4
        assert len(trail.trail) == 4
        assert len(trail.users_involved) == 1
        assert len(trail.change_summary) == 4
        assert trail.first_change is not None
        assert trail.last_change is not None
    
    def test_create_bulk_audit_logs(self, db, admin_user):
        """Test bulk audit log creation."""
        from app.schemas.audit_log import BulkAuditLogCreate, AuditLogCreate
        
        # Create bulk data
        logs = []
        for i in range(5):
            logs.append(AuditLogCreate(
                action=AuditAction.user_create,
                target_entity="user",
                actor_user_id=admin_user.id,
                target_id=uuid4(),
                changes_summary=f"Bulk created user {i+1}",
            ))
        
        bulk_data = BulkAuditLogCreate(
            logs=logs,
            batch_id="test-batch-123",
        )
        
        # Create bulk logs
        result = create_bulk_audit_logs(db, bulk_data)
        
        assert result.batch_id == "test-batch-123"
        assert result.success_count == 5
        assert result.failure_count == 0
        assert result.total_count == 5
        assert len(result.errors) == 0


class TestAuditLoggerUtility:
    """Test audit logger utility functions."""
    
    def test_audit_logger_user_actions(self, db, admin_user, customer_user):
        """Test AuditLogger user action methods."""
        
        # Test user creation log
        AuditLogger.log_user_action(
            db=db,
            action=AuditAction.user_create,
            user_id=admin_user.id,
            target_user_id=customer_user.id,
            changes_summary="Created new customer account",
        )
        
        # Verify log was created
        logs = get_audit_logs(db, limit=1)
        assert len(logs.logs) == 1
        log = logs.logs[0]
        assert log.action == AuditAction.user_create
        assert log.target_entity == "user"
        assert log.actor_user_id == admin_user.id
        assert log.target_user_id == customer_user.id
    
    def test_audit_logger_assessment_actions(self, db, admin_user):
        """Test AuditLogger assessment action methods."""
        
        assessment_id = uuid4()
        
        AuditLogger.log_assessment_action(
            db=db,
            action=AuditAction.assessment_submit,
            assessment_id=assessment_id,
            actor_user_id=admin_user.id,
            changes_summary="Submitted assessment for review",
        )
        
        # Verify log was created
        logs = get_audit_logs(db, limit=1)
        assert len(logs.logs) == 1
        log = logs.logs[0]
        assert log.action == AuditAction.assessment_submit
        assert log.target_entity == "assessment"
        assert log.target_id == assessment_id
    
    def test_create_changes_summary(self):
        """Test changes summary creation."""
        
        # Test with before and after data
        before = {"status": "pending", "score": 80}
        after = {"status": "completed", "score": 85}
        
        summary = AuditLogger.create_changes_summary(before, after)
        expected = "Changed status: pending → completed; Changed score: 80 → 85"
        assert summary == expected
        
        # Test with only after data
        after = {"status": "pending", "score": 90}
        summary = AuditLogger.create_changes_summary(None, after)
        expected = "Set status: pending; Set score: 90"
        assert summary == expected
        
        # Test with only before data
        before = {"status": "pending", "score": 80}
        summary = AuditLogger.create_changes_summary(before, None)
        expected = "Removed status: pending; Removed score: 80"
        assert summary == expected
        
        # Test with no data
        summary = AuditLogger.create_changes_summary(None, None, "Test action")
        assert summary == "Test action"
    
    def test_extract_sensitive_data(self):
        """Test sensitive data extraction."""
        
        data = {
            "username": "john_doe",
            "password": "secret123",
            "email": "john@example.com",
            "api_key": "abc123",
            "profile": {
                "name": "John Doe",
                "secret_token": "token456"
            },
            "permissions": ["read", "write"]
        }
        
        cleaned = AuditLogger.extract_sensitive_data(data)
        
        assert cleaned["username"] == "john_doe"
        assert cleaned["password"] == "[REDACTED]"
        assert cleaned["email"] == "john@example.com"
        assert cleaned["api_key"] == "[REDACTED]"
        assert cleaned["profile"]["name"] == "John Doe"
        assert cleaned["profile"]["secret_token"] == "[REDACTED]"
        assert cleaned["permissions"] == ["read", "write"]


class TestAuditLogAPI:
    """Test audit log API endpoints."""
    
    def test_get_audit_logs_endpoint(self, client, admin_token, admin_user):
        """Test GET /admin/audit-logs endpoint."""
        
        # Create some test logs
        from app.services.audit_log import create_audit_log
        from app.models.audit_log import AuditAction
        
        for i in range(3):
            create_audit_log(
                db=client.app.dependency_overrides[Session],
                action=AuditAction.user_create,
                target_entity="user",
                actor_user_id=admin_user.id,
                target_id=uuid4(),
                changes_summary=f"Created user {i+1}",
            )
        
        response = client.get(
            "/api/v1/admin/audit-logs/",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert len(data["logs"]) >= 3
    
    def test_get_audit_summary_endpoint(self, client, admin_token, admin_user):
        """Test GET /admin/audit-logs/summary/dashboard endpoint."""
        
        response = client.get(
            "/api/v1/admin/audit-logs/summary/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_logs" in data
        assert "successful_actions" in data
        assert "failed_actions" in data
        assert "unique_users" in data
        assert "most_common_actions" in data
        assert "recent_activity" in data
    
    def test_get_recent_changes_endpoint(self, client, admin_token):
        """Test GET /admin/audit-logs/recent-changes endpoint."""
        
        response = client.get(
            "/api/v1/admin/audit-logs/recent-changes",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "changes" in data
        assert "total" in data
        assert "time_period" in data
        assert "generated_at" in data
    
    def test_get_login_activity_endpoint(self, client, admin_token):
        """Test GET /admin/audit-logs/login-activity endpoint."""
        
        response = client.get(
            "/api/v1/admin/audit-logs/login-activity",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
    
    def test_get_failed_actions_endpoint(self, client, admin_token):
        """Test GET /admin/audit-logs/failed-actions endpoint."""
        
        response = client.get(
            "/api/v1/admin/audit-logs/failed-actions",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
    
    def test_get_user_activity_endpoint(self, client, admin_token, admin_user):
        """Test GET /admin/audit-logs/users/{user_id}/activity endpoint."""
        
        response = client.get(
            f"/api/v1/admin/audit-logs/users/{admin_user.id}/activity",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "user_name" in data
        assert "user_email" in data
        assert "total_actions" in data
        assert "successful_actions" in data
        assert "failed_actions" in data
    
    def test_get_entity_activity_endpoint(self, client, admin_token):
        """Test GET /admin/audit-logs/entities/{entity_type}/{entity_id}/activity endpoint."""
        
        entity_id = uuid4()
        
        response = client.get(
            f"/api/v1/admin/audit-logs/entities/assessment/{entity_id}/activity",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "entity_type" in data
        assert "entity_id" in data
        assert "total_changes" in data
        assert "changed_by_users" in data
    
    def test_get_entity_audit_trail_endpoint(self, client, admin_token):
        """Test GET /admin/audit-logs/entities/{entity_type}/{entity_id}/trail endpoint."""
        
        entity_id = uuid4()
        
        response = client.get(
            f"/api/v1/admin/audit-logs/entities/assessment/{entity_id}/trail",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "entity_type" in data
        assert "entity_id" in data
        assert "trail" in data
        assert "total_changes" in data
        assert "users_involved" in data
    
    def test_get_stats_endpoints(self, client, admin_token):
        """Test statistics endpoints."""
        
        # Test actions by hour
        response = client.get(
            "/api/v1/admin/audit-logs/stats/actions-by-hour",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Test actions by entity
        response = client.get(
            "/api/v1/admin/audit-logs/stats/actions-by-entity",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Test top users
        response = client.get(
            "/api/v1/admin/audit-logs/stats/top-users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
