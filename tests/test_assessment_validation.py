import pytest
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

from app.models.assessment import Assessment, AssessmentStatus, AssessmentAnswer
from app.models.checklist import Checklist, ChecklistSection, ChecklistQuestion, ChecklistStatus
from app.models.user import User, UserRole
from app.services.assessment import submit_assessment

class DummyDB:
    def __init__(self):
        self._objs = []
    def add(self, obj):
        self._objs.append(obj)
    def commit(self):
        pass
    def refresh(self, obj):
        pass
    def scalar(self, stmt):
        # Patch: Return correct Assessment for assessment_id and user_id
        from app.models.assessment import Assessment
        from sqlalchemy import Select
        # Handle select(Assessment).where(Assessment.id == ..., Assessment.user_id == ...)
        if isinstance(stmt, Select) and hasattr(stmt, 'column_descriptions') and stmt.column_descriptions:
            entity = stmt.column_descriptions[0]["entity"]
            if entity is Assessment:
                # Extract assessment_id and user_id from whereclause
                clauses = list(getattr(stmt, 'whereclause', []))
                assessment_id = None
                user_id = None
                for clause in clauses:
                    clause_str = str(clause)
                    if 'assessments.id' in clause_str:
                        assessment_id = clause.right.value if hasattr(clause.right, 'value') else None
                    if 'user_id' in clause_str:
                        user_id = clause.right.value if hasattr(clause.right, 'value') else None
                for a in self._objs:
                    if isinstance(a, Assessment) and (assessment_id is None or a.id == assessment_id) and (user_id is None or a.user_id == user_id):
                        return a
        # Only supports AssessmentAnswer.question_id for this test
        if hasattr(stmt, 'whereclause') and 'assessment_id' in str(stmt.whereclause):
            # Return all answered question_ids
            return [a.question_id for a in self._objs if isinstance(a, AssessmentAnswer)]
        return None
    def execute(self, stmt):
        # Simulate select for ChecklistSection and ChecklistQuestion
        if 'checklist_sections' in str(stmt):
            # Return section ids in order
            return DummyResult([s.id for s in self._objs if isinstance(s, ChecklistSection)])
        if 'checklist_questions' in str(stmt):
            # Return (id, parent_question_id) tuples in order
            return DummyResult([(q.id, q.parent_question_id) for q in self._objs if isinstance(q, ChecklistQuestion)])
        return DummyResult([])

class DummyResult:
    def __init__(self, vals):
        self._vals = vals
    def scalars(self):
        return self
    def all(self):
        return self._vals


def make_assessment_with_structure():
    user = User(id=uuid4(), email="u@example.com", password_hash="x", role=UserRole.customer, is_active=True)
    checklist = Checklist(id=uuid4(), checklist_type_id=uuid4(), version=1, status=ChecklistStatus.published, created_by=user.id, updated_by=user.id)
    section1 = ChecklistSection(id=uuid4(), checklist_id=checklist.id, section_code="S1", display_order=1)
    # Only one section for most tests
    q1 = ChecklistQuestion(id=uuid4(), checklist_id=checklist.id, section_id=section1.id, parent_question_id=None, question_code="Q1", display_order=1)
    q1_1 = ChecklistQuestion(id=uuid4(), checklist_id=checklist.id, section_id=section1.id, parent_question_id=q1.id, question_code="Q1.1", display_order=2)
    q2 = ChecklistQuestion(id=uuid4(), checklist_id=checklist.id, section_id=section1.id, parent_question_id=None, question_code="Q2", display_order=3)
    # For section order test, add a second section and question
    section2 = ChecklistSection(id=uuid4(), checklist_id=checklist.id, section_code="S2", display_order=2)
    q3 = ChecklistQuestion(id=uuid4(), checklist_id=checklist.id, section_id=section2.id, parent_question_id=None, question_code="Q3", display_order=1)
    assessment = Assessment(id=uuid4(), user_id=user.id, checklist_id=checklist.id, access_window_id=uuid4(), started_at=datetime.now(timezone.utc), status=AssessmentStatus.in_progress, expires_at=datetime.now(timezone.utc) + timedelta(days=1), completion_percent=0)
    return user, checklist, section1, section2, q1, q1_1, q2, q3, assessment


def test_submit_assessment_requires_parent_questions():
    db = DummyDB()
    user, checklist, section1, section2, q1, q1_1, q2, q3, assessment = make_assessment_with_structure()
    db.add(user)
    db.add(checklist)
    db.add(section1)
    db.add(q1)
    db.add(q1_1)
    db.add(q2)
    db.add(assessment)
    # Only answer sub-question, not parent
    db.add(AssessmentAnswer(assessment_id=assessment.id, question_id=q1_1.id, answer_score=4))
    with pytest.raises(HTTPException) as exc:
        submit_assessment(db, user=user, assessment_id=assessment.id)
    assert "parent questions must be answered" in str(exc.value.detail)


def test_submit_assessment_section_order():
    db = DummyDB()
    user, checklist, section1, section2, q1, q1_1, q2, q3, assessment = make_assessment_with_structure()
    db.add(user)
    db.add(checklist)
    db.add(section1)
    db.add(section2)
    db.add(q1)
    db.add(q1_1)
    db.add(q2)
    db.add(q3)
    db.add(assessment)
    # Answer only section 1 questions
    db.add(AssessmentAnswer(assessment_id=assessment.id, question_id=q1.id, answer_score=4))
    db.add(AssessmentAnswer(assessment_id=assessment.id, question_id=q2.id, answer_score=4))
    # Try to answer section 2 question without completing section 1
    db.add(AssessmentAnswer(assessment_id=assessment.id, question_id=q3.id, answer_score=4))
    with pytest.raises(HTTPException) as exc:
        submit_assessment(db, user=user, assessment_id=assessment.id)
    assert "Section 2 cannot be started until previous section is complete" in str(exc.value.detail)


def test_submit_assessment_question_order():
    db = DummyDB()
    user, checklist, section1, section2, q1, q1_1, q2, q3, assessment = make_assessment_with_structure()
    db.add(user)
    db.add(checklist)
    db.add(section1)
    db.add(q1)
    db.add(q1_1)
    db.add(q2)
    db.add(assessment)
    # Answer Q2 before Q1, then answer sub-question after both parents
    db.add(AssessmentAnswer(assessment_id=assessment.id, question_id=q2.id, answer_score=4))
    db.add(AssessmentAnswer(assessment_id=assessment.id, question_id=q1.id, answer_score=4))
    db.add(AssessmentAnswer(assessment_id=assessment.id, question_id=q1_1.id, answer_score=4))
    with pytest.raises(HTTPException) as exc:
        submit_assessment(db, user=user, assessment_id=assessment.id)
    assert "Question order violated" in str(exc.value.detail)


def test_submit_assessment_success():
    db = DummyDB()
    user, checklist, section1, section2, q1, q1_1, q2, q3, assessment = make_assessment_with_structure()
    db.add(user)
    db.add(checklist)
    db.add(section1)
    db.add(q1)
    db.add(q1_1)
    db.add(q2)
    db.add(assessment)
    # Answer all parent questions in order
    db.add(AssessmentAnswer(assessment_id=assessment.id, question_id=q1.id, answer_score=4))
    db.add(AssessmentAnswer(assessment_id=assessment.id, question_id=q2.id, answer_score=4))
    db.add(AssessmentAnswer(assessment_id=assessment.id, question_id=q1_1.id, answer_score=4))
    # Should succeed
    resp = submit_assessment(db, user=user, assessment_id=assessment.id)
    assert resp.status == AssessmentStatus.submitted
