"""Tests for assessment review functionality."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.models.assessment import Assessment, AssessmentStatus, AssessmentAnswer
from app.models.assessment_review import (
    AssessmentReview, 
    AnswerReview, 
    ReviewStatus, 
    SuggestionType
)
from app.models.checklist import Checklist, ChecklistQuestion, ChecklistSection
from app.models.user import User, UserRole
from app.schemas.assessment_review import (
    AnswerReviewCreate,
    AssessmentReviewUpdate,
    AnswerReviewResponse,
    AssessmentAnswerListResponse,
    ReviewSummary,
)


class TestAssessmentReview:
    """Test assessment review functionality."""
    
    def test_get_assessment_for_review(self, db, admin_user, customer_user, sample_checklist):
        """Test getting assessment for review."""
        # Create assessment
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),  # Mock access window
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.commit()
        
        # Test getting assessment for review
        from app.services.assessment_review import get_assessment_for_review
        
        result = get_assessment_for_review(db, assessment.id)
        
        assert result is not None
        assert result.id == assessment.id
        assert result.status == AssessmentStatus.submitted
        assert result.user.id == customer_user.id
    
    def test_get_assessment_answers_with_reviews(self, db, admin_user, customer_user, sample_checklist):
        """Test getting assessment answers with reviews."""
        # Create assessment with answers
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.flush()
        
        # Create answer
        answer = AssessmentAnswer(
            assessment_id=assessment.id,
            question_id=sample_checklist.questions[0].id,
            answer_score=5,
        )
        db.add(answer)
        db.commit()
        
        # Test getting answers with reviews
        from app.services.assessment_review import get_assessment_answers_with_reviews
        
        result = get_assessment_answers_with_reviews(db, assessment.id, admin_user.id)
        
        assert isinstance(result, AssessmentAnswerListResponse)
        assert result.assessment_id == assessment.id
        assert result.customer_email == customer_user.email
        assert len(result.answers) == 1
        assert result.answers[0].answer_id == answer.id
        assert result.answers[0].has_review == False
    
    def test_create_answer_review(self, db, admin_user, customer_user, sample_checklist):
        """Test creating answer review."""
        # Create assessment with answer
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.flush()
        
        answer = AssessmentAnswer(
            assessment_id=assessment.id,
            question_id=sample_checklist.questions[0].id,
            answer_score=5,
        )
        db.add(answer)
        db.commit()
        
        # Create review
        review_data = AnswerReviewCreate(
            suggestion_type=SuggestionType.IMPROVEMENT,
            suggestion_text="Consider adding more detail to your answer.",
            is_action_required=True,
            priority_level=3,
        )
        
        from app.services.assessment_review import create_answer_review
        
        result = create_answer_review(db, assessment.id, answer.id, admin_user.id, review_data)
        
        assert isinstance(result, AnswerReviewResponse)
        assert result.answer_id == answer.id
        assert result.suggestion_type == SuggestionType.IMPROVEMENT
        assert result.is_action_required == True
        assert result.priority_level == 3
        
        # Verify assessment review was created
        assessment_review = db.query(AssessmentReview).filter(AssessmentReview.assessment_id == assessment.id).first()
        assert assessment_review is not None
        assert assessment_review.status == ReviewStatus.IN_PROGRESS
    
    def test_update_answer_review(self, db, admin_user, customer_user, sample_checklist):
        """Test updating answer review."""
        # Create assessment, answer, and review
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.flush()
        
        answer = AssessmentAnswer(
            assessment_id=assessment.id,
            question_id=sample_checklist.questions[0].id,
            answer_score=5,
        )
        db.add(answer)
        db.flush()
        
        # Create initial review
        review_data = AnswerReviewCreate(
            suggestion_type=SuggestionType.IMPROVEMENT,
            suggestion_text="Original suggestion",
            priority_level=2,
        )
        
        from app.services.assessment_review import create_answer_review, update_answer_review
        
        original_review = create_answer_review(db, assessment.id, answer.id, admin_user.id, review_data)
        
        # Update review
        update_data = AnswerReviewUpdate(
            suggestion_text="Updated suggestion with more detail",
            priority_level=4,
            is_action_required=True,
        )
        
        result = update_answer_review(db, original_review.id, admin_user.id, update_data)
        
        assert result.id == original_review.id
        assert result.suggestion_text == "Updated suggestion with more detail"
        assert result.priority_level == 4
        assert result.is_action_required == True
    
    def test_delete_answer_review(self, db, admin_user, customer_user, sample_checklist):
        """Test deleting answer review."""
        # Create assessment, answer, and review
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.flush()
        
        answer = AssessmentAnswer(
            assessment_id=assessment.id,
            question_id=sample_checklist.questions[0].id,
            answer_score=5,
        )
        db.add(answer)
        db.flush()
        
        review_data = AnswerReviewCreate(
            suggestion_type=SuggestionType.BEST_PRACTICE,
            suggestion_text="This is a best practice suggestion",
        )
        
        from app.services.assessment_review import create_answer_review, delete_answer_review
        
        created_review = create_answer_review(db, assessment.id, answer.id, admin_user.id, review_data)
        
        # Delete review
        result = delete_answer_review(db, created_review.id, admin_user.id)
        
        assert result is True
        
        # Verify review is deleted
        deleted_review = db.query(AnswerReview).filter(AnswerReview.id == created_review.id).first()
        assert deleted_review is None
    
    def test_update_assessment_review(self, db, admin_user, customer_user, sample_checklist):
        """Test updating overall assessment review."""
        # Create assessment
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.commit()
        
        # Update assessment review
        review_data = AssessmentReviewUpdate(
            overall_score=85,
            max_score=100,
            completion_percentage=100.0,
            summary_notes="Good overall performance",
            strengths="Strong understanding of core concepts",
            improvement_areas="Could improve documentation",
            recommendations="Continue focusing on best practices",
        )
        
        from app.services.assessment_review import update_assessment_review
        
        result = update_assessment_review(db, assessment.id, admin_user.id, review_data)
        
        assert result.assessment_id == assessment.id
        assert result.overall_score == 85
        assert result.max_score == 100
        assert result.completion_percentage == 100.0
        assert result.summary_notes == "Good overall performance"
        assert result.strengths == "Strong understanding of core concepts"
        assert result.improvement_areas == "Could improve documentation"
        assert result.recommendations == "Continue focusing on best practices"
        assert result.reviewed_at is not None
    
    def test_get_review_summary(self, db, admin_user, customer_user, sample_checklist):
        """Test getting review summary."""
        # Create some test data
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.flush()
        
        # Create assessment review
        assessment_review = AssessmentReview(
            assessment_id=assessment.id,
            reviewer_id=admin_user.id,
            status=ReviewStatus.IN_PROGRESS,
        )
        db.add(assessment_review)
        db.flush()
        
        # Create answer review
        answer = AssessmentAnswer(
            assessment_id=assessment.id,
            question_id=sample_checklist.questions[0].id,
            answer_score=5,
        )
        db.add(answer)
        db.flush()
        
        answer_review = AnswerReview(
            assessment_review_id=assessment_review.id,
            answer_id=answer.id,
            reviewer_id=admin_user.id,
            suggestion_type=SuggestionType.IMPROVEMENT,
            suggestion_text="Test suggestion",
            is_action_required=True,
            priority_level=3,
        )
        db.add(answer_review)
        db.commit()
        
        # Get summary
        from app.services.assessment_review import get_review_summary
        
        result = get_review_summary(db)
        
        assert isinstance(result, ReviewSummary)
        assert result.total_assessments_in_progress == 1
        assert result.total_answer_reviews == 1
        assert result.total_action_required == 1
        assert len(result.recent_reviews) == 1


class TestAssessmentReviewAPI:
    """Test assessment review API endpoints."""
    
    def test_get_review_summary_endpoint(self, client, admin_token, admin_user):
        """Test GET /admin/assessment-review/summary endpoint."""
        response = client.get(
            "/api/v1/admin/assessment-review/summary",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_assessments_pending_review" in data
        assert "total_assessments_in_progress" in data
        assert "total_assessments_completed" in data
        assert "total_answer_reviews" in data
        assert "recent_reviews" in data
    
    def test_get_assessment_reviews_endpoint(self, client, admin_token, admin_user, customer_user, sample_checklist):
        """Test GET /admin/assessment-review/assessments endpoint."""
        # Create test assessment
        from app.models.assessment import Assessment
        from app.models.assessment_review import AssessmentReview, ReviewStatus
        
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.flush()
        
        assessment_review = AssessmentReview(
            assessment_id=assessment.id,
            reviewer_id=admin_user.id,
            status=ReviewStatus.IN_PROGRESS,
        )
        db.add(assessment_review)
        db.commit()
        
        response = client.get(
            "/api/v1/admin/assessment-review/assessments",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_get_assessment_answers_endpoint(self, client, admin_token, admin_user, customer_user, sample_checklist):
        """Test GET /admin/assessment-review/assessment/{assessment_id} endpoint."""
        # Create assessment with answers
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.flush()
        
        answer = AssessmentAnswer(
            assessment_id=assessment.id,
            question_id=sample_checklist.questions[0].id,
            answer_score=5,
        )
        db.add(answer)
        db.commit()
        
        response = client.get(
            f"/api/v1/admin/assessment-review/assessment/{assessment.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["assessment_id"] == str(assessment.id)
        assert data["customer_email"] == customer_user.email
        assert "answers" in data
        assert len(data["answers"]) == 1
    
    def test_create_answer_review_endpoint(self, client, admin_token, admin_user, customer_user, sample_checklist):
        """Test POST /admin/assessment-review/answer/{answer_id}/review endpoint."""
        # Create assessment with answer
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.flush()
        
        answer = AssessmentAnswer(
            assessment_id=assessment.id,
            question_id=sample_checklist.questions[0].id,
            answer_score=5,
        )
        db.add(answer)
        db.commit()
        
        review_data = {
            "suggestion_type": "improvement",
            "suggestion_text": "Consider adding more examples to support your answer.",
            "is_action_required": True,
            "priority_level": 3,
            "reference_materials": "https://example.com/best-practices"
        }
        
        response = client.post(
            f"/api/v1/admin/assessment-review/answer/{answer.id}/review",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=review_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer_id"] == str(answer.id)
        assert data["suggestion_type"] == "improvement"
        assert data["suggestion_text"] == "Consider adding more examples to support your answer."
        assert data["is_action_required"] == True
        assert data["priority_level"] == 3
    
    def test_update_answer_review_endpoint(self, client, admin_token, admin_user, customer_user, sample_checklist):
        """Test PUT /admin/assessment-review/answer-review/{review_id} endpoint."""
        # Create assessment, answer, and review
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.flush()
        
        answer = AssessmentAnswer(
            assessment_id=assessment.id,
            question_id=sample_checklist.questions[0].id,
            answer_score=5,
        )
        db.add(answer)
        db.flush()
        
        # Create initial review
        review_data = {
            "suggestion_type": "improvement",
            "suggestion_text": "Original suggestion",
            "priority_level": 2,
        }
        
        response = client.post(
            f"/api/v1/admin/assessment-review/answer/{answer.id}/review",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=review_data
        )
        
        original_review = response.json()
        
        # Update review
        update_data = {
            "suggestion_text": "Updated suggestion with more detail",
            "priority_level": 4,
            "is_action_required": True,
        }
        
        response = client.put(
            f"/api/v1/admin/assessment-review/answer-review/{original_review['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == original_review["id"]
        assert data["suggestion_text"] == "Updated suggestion with more detail"
        assert data["priority_level"] == 4
        assert data["is_action_required"] == True
    
    def test_quick_approve_assessment(self, client, admin_token, admin_user, customer_user, sample_checklist):
        """Test POST /admin/assessment-review/assessment/{assessment_id}/quick-approve endpoint."""
        # Create assessment
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.commit()
        
        response = client.post(
            f"/api/v1/admin/assessment-review/assessment/{assessment.id}/quick-approve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["assessment_id"] == str(assessment.id)
        assert data["status"] == "completed"
        assert "quick approve" in data["summary_notes"].lower()
    
    def test_get_assessment_review_status(self, client, admin_token, admin_user, customer_user, sample_checklist):
        """Test GET /admin/assessment-review/assessment/{assessment_id}/status endpoint."""
        # Create assessment
        assessment = Assessment(
            user_id=customer_user.id,
            checklist_id=sample_checklist.id,
            access_window_id=uuid4(),
            status=AssessmentStatus.submitted,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(assessment)
        db.commit()
        
        response = client.get(
            f"/api/v1/admin/assessment-review/assessment/{assessment.id}/status",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["assessment_id"] == str(assessment.id)
        assert data["has_review"] == False
        assert data["status"] == "not_started"
