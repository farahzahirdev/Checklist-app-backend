"""Tests for customer multi-assessment management."""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from app.models.assessment import Assessment, AssessmentStatus
from app.models.checklist import Checklist, ChecklistStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.models.access_window import AccessWindow
from app.schemas.customer_assessments import (
    AssessmentSummary,
    CustomerAssessmentListResponse,
    CustomerAssessmentDashboardResponse,
)
from app.services.customer_assessments import (
    get_customer_assessments,
    get_assessment_detail,
    get_customer_dashboard_enhanced,
    perform_assessment_action,
)


class TestCustomerAssessments:
    """Test customer assessment management functionality."""
    
    def test_get_customer_assessments_empty(self, db, customer_user):
        """Test getting assessments when user has none."""
        result = get_customer_assessments(db, customer_user.id)
        
        assert isinstance(result, CustomerAssessmentListResponse)
        assert result.total == 0
        assert len(result.assessments) == 0
        assert result.generated_at is not None
    
    def test_get_customer_assessments_with_data(self, db, customer_user, sample_checklist):
        """Test getting assessments with actual data."""
        # Create payment and access window
        payment = Payment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            status=PaymentStatus.succeeded,
            amount_cents=1000,
            currency="USD",
        )
        db.add(payment)
        db.flush()
        
        access_window = AccessWindow(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            payment_id=payment.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(access_window)
        db.flush()
        
        # Create assessment
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=access_window.id,
            status=AssessmentStatus.in_progress,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            completion_percent=25.5,
        )
        db.add(assessment)
        db.commit()
        
        result = get_customer_assessments(db, customer_user.id)
        
        assert result.total == 1
        assert len(result.assessments) == 1
        
        assessment_summary = result.assessments[0]
        assert isinstance(assessment_summary, AssessmentSummary)
        assert assessment_summary.id == assessment.id
        assert assessment_summary.checklist_id == sample_checklist.id
        assert assessment_summary.status == AssessmentStatus.in_progress
        assert assessment_summary.completion_percent == 25.5
    
    def test_get_customer_assessments_filtering(self, db, customer_user, sample_checklist):
        """Test filtering assessments by status."""
        # Create multiple assessments with different statuses
        payment = Payment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            status=PaymentStatus.succeeded,
            amount_cents=1000,
            currency="USD",
        )
        db.add(payment)
        db.flush()
        
        access_window = AccessWindow(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            payment_id=payment.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(access_window)
        db.flush()
        
        # Create in-progress assessment
        assessment1 = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=access_window.id,
            status=AssessmentStatus.in_progress,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment1)
        
        # Create submitted assessment
        assessment2 = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=access_window.id,
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment2)
        db.commit()
        
        # Test filtering by status
        result = get_customer_assessments(
            db, 
            customer_user.id, 
            status_filter=[AssessmentStatus.in_progress]
        )
        
        assert result.total == 1
        assert result.assessments[0].status == AssessmentStatus.in_progress
    
    def test_get_assessment_detail(self, db, customer_user, sample_checklist):
        """Test getting detailed assessment information."""
        # Setup
        payment = Payment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            status=PaymentStatus.succeeded,
            amount_cents=1000,
            currency="USD",
        )
        db.add(payment)
        db.flush()
        
        access_window = AccessWindow(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            payment_id=payment.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(access_window)
        db.flush()
        
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=access_window.id,
            status=AssessmentStatus.in_progress,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            completion_percent=50.0,
        )
        db.add(assessment)
        db.commit()
        
        # Test
        result = get_assessment_detail(db, customer_user.id, assessment.id)
        
        assert result.id == assessment.id
        assert result.checklist_id == sample_checklist.id
        assert result.status == AssessmentStatus.in_progress
        assert result.completion_percent == 50.0
        assert result.total_questions >= 0  # Should be calculated from checklist
        assert result.sections_completed >= 0
    
    def test_get_assessment_detail_not_found(self, db, customer_user):
        """Test getting detail for non-existent assessment."""
        with pytest.raises(ValueError, match="Assessment not found"):
            get_assessment_detail(db, customer_user.id, uuid4())
    
    def test_get_customer_dashboard_enhanced(self, db, customer_user, sample_checklist):
        """Test enhanced customer dashboard."""
        # Setup payment and access window
        payment = Payment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            status=PaymentStatus.succeeded,
            amount_cents=1000,
            currency="USD",
        )
        db.add(payment)
        db.flush()
        
        access_window = AccessWindow(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            payment_id=payment.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(access_window)
        db.flush()
        
        # Create assessment
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=access_window.id,
            status=AssessmentStatus.in_progress,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.commit()
        
        # Test
        result = get_customer_dashboard_enhanced(db, customer_user.id)
        
        assert isinstance(result, CustomerAssessmentDashboardResponse)
        assert result.summary.total_purchased_checklists == 1
        assert result.summary.active_assessments_count == 1
        assert len(result.active_assessments) == 1
        assert len(result.available_checklists) == 1
        assert len(result.quick_actions) > 0
    
    def test_perform_assessment_action_extend(self, db, customer_user, sample_checklist):
        """Test extending assessment expiry."""
        # Setup
        payment = Payment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            status=PaymentStatus.succeeded,
            amount_cents=1000,
            currency="USD",
        )
        db.add(payment)
        db.flush()
        
        access_window = AccessWindow(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            payment_id=payment.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(access_window)
        db.flush()
        
        original_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=access_window.id,
            status=AssessmentStatus.in_progress,
            expires_at=original_expiry,
        )
        db.add(assessment)
        db.commit()
        
        # Test
        result = perform_assessment_action(
            db, 
            customer_user.id, 
            assessment.id, 
            "extend"
        )
        
        assert result.success is True
        assert result.action_performed == "extend"
        assert result.new_status == AssessmentStatus.in_progress
        assert result.updated_expires_at is not None
        assert result.updated_expires_at > original_expiry
    
    def test_perform_assessment_action_not_found(self, db, customer_user):
        """Test performing action on non-existent assessment."""
        with pytest.raises(ValueError, match="Assessment not found"):
            perform_assessment_action(db, customer_user.id, uuid4(), "extend")
    
    def test_perform_assessment_action_invalid_action(self, db, customer_user, sample_checklist):
        """Test performing invalid action."""
        # Setup
        payment = Payment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            status=PaymentStatus.succeeded,
            amount_cents=1000,
            currency="USD",
        )
        db.add(payment)
        db.flush()
        
        access_window = AccessWindow(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            payment_id=payment.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(access_window)
        db.flush()
        
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=access_window.id,
            status=AssessmentStatus.in_progress,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.commit()
        
        # Test
        with pytest.raises(ValueError, match="Unknown action"):
            perform_assessment_action(db, customer_user.id, assessment.id, "invalid_action")


class TestCustomerAssessmentAPI:
    """Test customer assessment API endpoints."""
    
    def test_list_assessments_endpoint(self, client, customer_token, customer_user, sample_checklist):
        """Test GET /customer/assessments endpoint."""
        # Setup
        from app.models.payment import Payment, PaymentStatus
        from app.models.access_window import AccessWindow
        from app.models.assessment import Assessment, AssessmentStatus
        
        payment = Payment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            status=PaymentStatus.succeeded,
            amount_cents=1000,
            currency="USD",
        )
        db.add(payment)
        db.flush()
        
        access_window = AccessWindow(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            payment_id=payment.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(access_window)
        db.flush()
        
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=access_window.id,
            status=AssessmentStatus.in_progress,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.commit()
        
        # Test
        response = client.get(
            "/api/v1/customer/assessments/",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["assessments"]) == 1
        assert "generated_at" in data
    
    def test_dashboard_enhanced_endpoint(self, client, customer_token):
        """Test GET /dashboard/customer/enhanced endpoint."""
        response = client.get(
            "/api/v1/dashboard/customer/enhanced",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "active_assessments" in data
        assert "available_checklists" in data
        assert "quick_actions" in data
        assert "generated_at" in data
    
    def test_assessment_detail_endpoint(self, client, customer_token, customer_user, sample_checklist):
        """Test GET /customer/assessments/{assessment_id} endpoint."""
        # Setup
        from app.models.payment import Payment, PaymentStatus
        from app.models.access_window import AccessWindow
        from app.models.assessment import Assessment, AssessmentStatus
        
        payment = Payment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            status=PaymentStatus.succeeded,
            amount_cents=1000,
            currency="USD",
        )
        db.add(payment)
        db.flush()
        
        access_window = AccessWindow(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            payment_id=payment.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(access_window)
        db.flush()
        
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=access_window.id,
            status=AssessmentStatus.in_progress,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.commit()
        
        # Test
        response = client.get(
            f"/api/v1/customer/assessments/{assessment.id}",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(assessment.id)
        assert data["checklist_id"] == str(sample_checklist.id)
        assert data["status"] == "in_progress"
        assert "total_questions" in data
        assert "sections_completed" in data
    
    def test_assessment_action_endpoint(self, client, customer_token, customer_user, sample_checklist):
        """Test POST /customer/assessments/{assessment_id}/action endpoint."""
        # Setup
        from app.models.payment import Payment, PaymentStatus
        from app.models.access_window import AccessWindow
        from app.models.assessment import Assessment, AssessmentStatus
        
        payment = Payment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            status=PaymentStatus.succeeded,
            amount_cents=1000,
            currency="USD",
        )
        db.add(payment)
        db.flush()
        
        access_window = AccessWindow(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            payment_id=payment.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(access_window)
        db.flush()
        
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=access_window.id,
            status=AssessmentStatus.in_progress,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.commit()
        
        # Test
        response = client.post(
            f"/api/v1/customer/assessments/{assessment.id}/action",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={"action": "extend", "reason": "Need more time"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action_performed"] == "extend"
        assert data["updated_expires_at"] is not None
