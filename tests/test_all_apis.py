"""
Comprehensive API Test Suite for Checklist App
Tests all API endpoints with real database integration
"""
import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.main import app
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.rbac import Role, UserRoleAssignment
from app.models.checklist import Checklist, ChecklistSection, ChecklistQuestion, ChecklistType
from app.models.payment import Payment
from app.models.assessment import Assessment, AssessmentAnswer
from app.models.media import Media

client = TestClient(app)

# Test data fixtures
@pytest.fixture(scope="function")
def db():
    """Database session for testing"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def admin_user(db):
    """Create admin user for testing"""
    # Check if user already exists and delete if needed
    existing_user = db.query(User).filter(User.email == "admin@test.com").first()
    if existing_user:
        # First delete any checklists created by this user
        from app.models.checklist import Checklist
        db.query(Checklist).filter(Checklist.created_by == existing_user.id).delete()
        db.delete(existing_user)
        db.commit()
    
    user = User(
        email="admin@test.com",
        password_hash=hash_password("Admin123!"),
        role=UserRole.admin,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture(scope="function")
def customer_user(db):
    """Create customer user for testing"""
    # Check if user already exists and delete if needed
    existing_user = db.query(User).filter(User.email == "customer@test.com").first()
    if existing_user:
        # First delete any related records
        from app.models.checklist import Checklist
        from app.models.assessment import Assessment
        db.query(Assessment).filter(Assessment.user_id == existing_user.id).delete()
        db.query(Checklist).filter(Checklist.created_by == existing_user.id).delete()
        db.delete(existing_user)
        db.commit()
    
    user = User(
        email="customer@test.com",
        password_hash=hash_password("Customer123!"),
        role=UserRole.customer,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture(scope="function")
def auditor_user(db):
    """Create auditor user for testing"""
    # Check if user already exists and delete if needed
    existing_user = db.query(User).filter(User.email == "auditor@test.com").first()
    if existing_user:
        # First delete any related records
        from app.models.checklist import Checklist
        from app.models.assessment import Assessment
        db.query(Assessment).filter(Assessment.user_id == existing_user.id).delete()
        db.query(Checklist).filter(Checklist.created_by == existing_user.id).delete()
        db.delete(existing_user)
        db.commit()
    
    user = User(
        email="auditor@test.com",
        password_hash=hash_password("Auditor123!"),
        role=UserRole.auditor,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture(scope="function")
def admin_token(admin_user):
    """Get admin auth token"""
    response = client.post("/api/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!"
    })
    return response.json()["access_token"]

@pytest.fixture(scope="function")
def customer_token(customer_user):
    """Get customer auth token"""
    response = client.post("/api/api/v1/auth/login", json={
        "email": "customer@test.com",
        "password": "Customer123!"
    })
    return response.json()["access_token"]

@pytest.fixture(scope="function")
def auditor_token(auditor_user):
    """Get auditor auth token"""
    response = client.post("/api/api/v1/auth/login", json={
        "email": "auditor@test.com",
        "password": "Auditor123!"
    })
    return response.json()["access_token"]

@pytest.fixture(scope="function")
def sample_checklist(db, admin_user):
    """Create sample checklist for testing"""
    # Check if checklist type already exists
    checklist_type = db.query(ChecklistType).filter(ChecklistType.code == "test_type").first()
    if not checklist_type:
        checklist_type = ChecklistType(
            code="test_type",
            name="Test Type",
            description="Test checklist type"
        )
        db.add(checklist_type)
        db.commit()
        db.refresh(checklist_type)
    
    # Create checklist
    checklist = Checklist(
        checklist_type_id=checklist_type.id,
        version="1.0",
        created_by=admin_user.id,
        updated_by=admin_user.id,
        status="draft"
    )
    db.add(checklist)
    db.commit()
    db.refresh(checklist)
    
    # Create section
    section = ChecklistSection(
        checklist_id=checklist.id,
        section_code="test_section",
        display_order=1
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    
    # Create question
    question = ChecklistQuestion(
        checklist_id=checklist.id,
        section_id=section.id,
        question_code="test_question",
        display_order=1,
        answer_logic="yes_no"
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    
    return checklist

class TestHealthAPI:
    """Test health check endpoints"""
    
    def test_health_check(self):
        """Test basic health check"""
        response = client.get("/api/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

class TestAuthAPI:
    """Test authentication endpoints"""
    
    def test_register_user(self):
        """Test user registration"""
        import time
        unique_email = f"newuser{int(time.time())}@test.com"
        response = client.post("/api/api/v1/auth/register", json={
            "email": unique_email,
            "password": "NewUser123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == unique_email
        assert data["user"]["role"] == 2
    
    def test_login_valid_credentials(self, customer_user):
        """Test login with valid credentials"""
        response = client.post("/api/api/v1/auth/login", json={
            "email": "customer@test.com",
            "password": "Customer123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "customer@test.com"
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = client.post("/api/api/v1/auth/login", json={
            "email": "nonexistent@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
    
    def test_get_current_user(self, customer_token):
        """Test getting current user info"""
        response = client.get("/api/api/v1/auth/me", headers={
            "Authorization": f"Bearer {customer_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "customer@test.com"
        assert data["user"]["role"] == 2

class TestPaymentsAPI:
    """Test payment endpoints"""
    
    @patch('app.services.stripe_products.stripe')
    def test_create_checkout_session(self, mock_stripe, customer_token):
        """Test creating Stripe checkout session"""
        # Mock Stripe response
        mock_stripe.checkout.Session.create.return_value = {
            "id": "cs_test_123",
            "url": "https://checkout.stripe.com/pay/cs_test_123"
        }
        
        response = client.post("/api/api/v1/payments/create-checkout-session", 
            headers={"Authorization": f"Bearer {customer_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "checkout_url" in data
    
    @patch('app.services.stripe_products.stripe')
    def test_stripe_webhook(self, mock_stripe):
        """Test Stripe webhook processing"""
        # Mock webhook event
        mock_stripe.Webhook.construct_event.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "customer": "cus_test_123",
                    "payment_status": "paid"
                }
            }
        }
        
        response = client.post("/api/api/v1/payments/webhook",
            headers={"stripe-signature": "test_signature"},
            json={"test": "data"}
        )
        assert response.status_code == 200

class TestAssessmentAPI:
    """Test assessment endpoints"""
    
    def test_start_assessment(self, customer_token, sample_checklist):
        """Test starting an assessment"""
        response = client.post("/api/api/v1/assessment/start", 
            headers={"Authorization": f"Bearer {customer_token}"},
            json={"checklist_id": str(sample_checklist.id)}
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "checklist" in data
    
    def test_save_answer(self, customer_token, sample_checklist):
        """Test saving assessment answer"""
        # First start assessment
        start_response = client.post("/api/api/v1/assessment/start", 
            headers={"Authorization": f"Bearer {customer_token}"},
            json={"checklist_id": str(sample_checklist.id)}
        )
        session_id = start_response.json()["session_id"]
        
        # Get question ID from checklist structure
        db = SessionLocal()
        question = db.query(ChecklistQuestion).filter_by(checklist_id=sample_checklist.id).first()
        db.close()
        
        # Save answer
        response = client.post("/api/api/v1/assessment/answer", 
            headers={"Authorization": f"Bearer {customer_token}"},
            json={
                "session_id": session_id,
                "question_id": str(question.id),
                "answer": {"value": "yes"}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_submit_assessment(self, customer_token, sample_checklist):
        """Test submitting assessment"""
        # First start assessment
        start_response = client.post("/api/api/v1/assessment/start", 
            headers={"Authorization": f"Bearer {customer_token}"},
            json={"checklist_id": str(sample_checklist.id)}
        )
        session_id = start_response.json()["session_id"]
        
        # Submit assessment
        response = client.post("/api/api/v1/assessment/submit", 
            headers={"Authorization": f"Bearer {customer_token}"},
            json={"session_id": session_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert "report_id" in data

class TestAdminChecklistsAPI:
    """Test admin checklist management endpoints"""
    
    def test_create_checklist(self, admin_token):
        """Test creating a new checklist"""
        response = client.post("/api/api/v1/admin/checklists", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "New Test Checklist",
                "description": "New Test Description",
                "sections": [
                    {
                        "title": "Test Section",
                        "description": "Test Section Description",
                        "questions": [
                            {
                                "title": "Test Question",
                                "description": "Test Question Description",
                                "question_type": "yes_no",
                                "is_required": True
                            }
                        ]
                    }
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Test Checklist"
        assert len(data["sections"]) == 1
    
    def test_get_checklists(self, admin_token, sample_checklist):
        """Test getting all checklists"""
        response = client.get("/api/api/v1/admin/checklists", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "checklists" in data
        assert len(data["checklists"]) >= 1
        assert any(c["title"] == "Test Checklist" for c in data["checklists"])
    
    def test_update_checklist(self, admin_token, sample_checklist):
        """Test updating a checklist"""
        response = client.put(f"/api/api/v1/admin/checklists/{sample_checklist.id}", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Updated Test Checklist",
                "description": "Updated Test Description"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Test Checklist"
    
    def test_delete_checklist(self, admin_token, sample_checklist):
        """Test deleting a checklist"""
        response = client.delete(f"/api/api/v1/admin/checklists/{sample_checklist.id}", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200

class TestDashboardAPI:
    """Test dashboard endpoints"""
    
    def test_admin_dashboard(self, admin_token):
        """Test admin dashboard"""
        response = client.get("/api/api/v1/dashboard/admin", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "assessments_submitted" in data
        assert "checklists_published" in data
        assert "customers_total" in data
    
    def test_customer_dashboard(self, customer_token):
        """Test customer dashboard"""
        response = client.get("/api/api/v1/dashboard/customer", 
            headers={"Authorization": f"Bearer {customer_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "active_assessments_count" in data
        assert "paid_checklists_count" in data
    
    def test_auditor_dashboard(self, auditor_token):
        """Test auditor dashboard"""
        response = client.get("/api/api/v1/dashboard/auditor", 
            headers={"Authorization": f"Bearer {auditor_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "draft_reports_waiting" in data
        assert "reports_changes_requested" in data

class TestRBACAPI:
    """Test role-based access control endpoints"""
    
    def test_get_permissions(self, admin_token):
        """Test getting all permissions"""
        response = client.get("/api/api/v1/admin/rbac/permissions", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_roles(self, admin_token):
        """Test getting all roles"""
        response = client.get("/api/api/v1/admin/rbac/roles", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(role["code"] == "admin" for role in data)
    
    def test_check_permission(self, admin_token):
        """Test checking user permissions"""
        response = client.post("/api/api/v1/admin/rbac/check-permission", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"permission": "admin:access"})
        assert response.status_code == 200
        data = response.json()
        assert data["has_permission"] is True

class TestUserManagementAPI:
    """Test user management endpoints"""
    
    def test_get_users(self, admin_token):
        """Test getting all users"""
        response = client.get("/api/api/v1/user-management/users", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_update_user_role(self, admin_token, customer_user):
        """Test updating user role"""
        response = client.put(f"/api/api/v1/user-management/users/{customer_user.id}/role", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"role": "auditor"})
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "auditor"
    
    def test_get_customers(self, admin_token):
        """Test getting all customers"""
        response = client.get("/api/api/v1/user-management/customers", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

class TestReportsAPI:
    """Test report endpoints"""
    
    def test_generate_draft_report(self, admin_token, sample_checklist, customer_user):
        """Test generating draft report"""
        # Create assessment first
        assessment = Assessment(
            checklist_id=sample_checklist.id,
            user_id=customer_user.id,
            access_window_id=uuid4(),  # Mock access window ID
            status="submitted"
        )
        db = SessionLocal()
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        db.close()
        
        response = client.post("/api/api/v1/reports/generate-draft", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"assessment_id": str(assessment.id)})
        assert response.status_code == 200
        data = response.json()
        assert "report_id" in data
    
    def test_get_reports(self, admin_token):
        """Test getting all reports"""
        response = client.get("/api/api/v1/reports", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

class TestMediaAPI:
    """Test media upload endpoints"""
    
    def test_upload_media(self, admin_token):
        """Test media file upload"""
        # Create a mock file
        files = {"file": ("test.jpg", b"fake image data", "image/jpeg")}
        response = client.post("/api/api/v1/media/upload", 
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files)
        assert response.status_code == 200
        data = response.json()
        assert "media_id" in data
        assert data["filename"] == "test.jpg"
    
    def test_get_media(self, admin_token):
        """Test getting media info"""
        # First upload a file
        files = {"file": ("test2.jpg", b"fake image data", "image/jpeg")}
        upload_response = client.post("/api/api/v1/media/upload", 
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files)
        media_id = upload_response.json()["media_id"]
        
        # Get media info
        response = client.get(f"/api/api/v1/media/{media_id}", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test2.jpg"

class TestAccessAPI:
    """Test access control endpoints"""
    
    def test_create_access_window(self, admin_token, customer_user):
        """Test creating access window"""
        response = client.post("/api/api/v1/access/window", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "user_id": str(customer_user.id),
                "unlock_days": 30
            })
        assert response.status_code == 200
        data = response.json()
        assert "access_window_id" in data
    
    def test_get_access_status(self, customer_token):
        """Test getting access status"""
        response = client.get("/api/api/v1/access/status", 
            headers={"Authorization": f"Bearer {customer_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "has_access" in data

class TestCustomerChecklistsAPI:
    """Test customer checklist endpoints"""
    
    def test_get_available_checklists(self, customer_token):
        """Test getting available checklists for customer"""
        response = client.get("/api/api/v1/checklists/available", 
            headers={"Authorization": f"Bearer {customer_token}"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_checklist_details(self, customer_token, sample_checklist):
        """Test getting checklist details"""
        response = client.get(f"/api/api/v1/checklists/{sample_checklist.id}", 
            headers={"Authorization": f"Bearer {customer_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_checklist.id)

# Integration Tests
class TestAPIIntegration:
    """Test API integration scenarios"""
    
    def test_complete_user_journey(self):
        """Test complete user journey from registration to assessment"""
        # 1. Register new user
        register_response = client.post("/api/api/v1/auth/register", json={
            "email": "journey@test.com",
            "password": "Journey123!"
        })
        assert register_response.status_code == 200
        token = register_response.json()["access_token"]
        
        # 2. Get available checklists
        checklists_response = client.get("/api/api/v1/checklists/available", 
            headers={"Authorization": f"Bearer {token}"})
        assert checklists_response.status_code == 200
        
        # 3. Start assessment (if checklists available)
        if checklists_response.json():
            checklist_id = checklists_response.json()[0]["id"]
            start_response = client.post("/api/api/v1/assessment/start", 
                headers={"Authorization": f"Bearer {token}"},
                json={"checklist_id": checklist_id})
            assert start_response.status_code == 200
    
    def test_admin_workflow(self, admin_token):
        """Test admin workflow for checklist management"""
        # 1. Create checklist
        create_response = client.post("/api/api/v1/admin/checklists", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Workflow Test Checklist",
                "description": "Testing admin workflow",
                "sections": [
                    {
                        "title": "Workflow Section",
                        "questions": [
                            {
                                "title": "Workflow Question",
                                "question_type": "yes_no",
                                "is_required": True
                            }
                        ]
                    }
                ]
            })
        assert create_response.status_code == 200
        checklist_id = create_response.json()["id"]
        
        # 2. Update checklist
        update_response = client.put(f"/api/api/v1/admin/checklists/{checklist_id}", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"title": "Updated Workflow Checklist"})
        assert update_response.status_code == 200
        
        # 3. Get dashboard stats
        dashboard_response = client.get("/api/api/v1/dashboard/admin", 
            headers={"Authorization": f"Bearer {admin_token}"})
        assert dashboard_response.status_code == 200

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
