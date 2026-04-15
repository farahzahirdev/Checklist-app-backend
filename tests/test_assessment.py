from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.models.access_window import AccessWindow
from app.models.assessment import Assessment, AssessmentStatus
from app.models.checklist import Checklist, ChecklistStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.services.assessment import get_current_assessment, start_assessment


class FakeSession:
    def __init__(self) -> None:
        self.users: list[User] = []
        self.checklists: list[Checklist] = []
        self.payments: list[Payment] = []
        self.access_windows: list[AccessWindow] = []
        self.assessments: list[Assessment] = []

    def add(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if isinstance(obj, User):
            if obj.is_active is None:
                obj.is_active = True
            self.users.append(obj)
        elif isinstance(obj, Checklist):
            self.checklists.append(obj)
        elif isinstance(obj, Payment):
            self.payments.append(obj)
        elif isinstance(obj, AccessWindow):
            self.access_windows.append(obj)
        elif isinstance(obj, Assessment):
            self.assessments.append(obj)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def refresh(self, obj) -> None:
        return None

    def get(self, model, object_id):
        if model is Checklist:
            return next((item for item in self.checklists if item.id == object_id), None)
        if model is User:
            return next((item for item in self.users if item.id == object_id), None)
        return None

    def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        params = statement.compile().params

        if entity is Payment:
            user_id = _extract_uuid(params, "user_id")
            checklist_id = _extract_uuid(params, "checklist_id")
            candidates = [
                item
                for item in self.payments
                if item.user_id == user_id
                and item.status == PaymentStatus.succeeded
                and (checklist_id is None or item.checklist_id == checklist_id)
            ]
            candidates.sort(key=lambda item: item.paid_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            return candidates[0] if candidates else None

        if entity is AccessWindow:
            user_id = _extract_uuid(params, "user_id")
            now = _extract_datetime(params)
            candidates = [item for item in self.access_windows if item.user_id == user_id and item.expires_at > now]
            candidates.sort(key=lambda item: item.expires_at, reverse=True)
            return candidates[0] if candidates else None

        if entity is Assessment:
            user_id = _extract_uuid(params, "user_id")
            checklist_id = _extract_uuid(params, "checklist_id")
            now = _extract_datetime(params)
            candidates = [
                item
                for item in self.assessments
                if item.user_id == user_id
                and item.expires_at > now
                and item.status in {AssessmentStatus.not_started, AssessmentStatus.in_progress}
                and (checklist_id is None or item.checklist_id == checklist_id)
            ]
            candidates.sort(key=lambda item: item.created_at or now, reverse=True)
            return candidates[0] if candidates else None

        return None


def _extract_uuid(params: dict, keyword: str) -> UUID | None:
    for key, value in params.items():
        if keyword in key:
            return UUID(str(value)) if isinstance(value, str) else value
    return None


def _extract_datetime(params: dict) -> datetime:
    for key, value in params.items():
        if isinstance(value, datetime):
            return value
    return datetime.now(timezone.utc)


def test_start_assessment_requires_payment() -> None:
    db = FakeSession()
    user = User(id=uuid4(), email="u@example.com", password_hash="x", role=UserRole.customer, is_active=True)
    checklist = Checklist(
        id=uuid4(),
        checklist_type_id=uuid4(),
        version=1,
        status=ChecklistStatus.published,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(user)
    db.add(checklist)

    with pytest.raises(HTTPException) as exc:
        start_assessment(db, user=user, checklist_id=checklist.id)

    assert exc.value.status_code == 403
    assert exc.value.detail == "payment_required"


def test_start_assessment_creates_session_and_is_idempotent() -> None:
    db = FakeSession()
    now = datetime.now(timezone.utc)
    user = User(id=uuid4(), email="u@example.com", password_hash="x", role=UserRole.customer, is_active=True)
    checklist = Checklist(
        id=uuid4(),
        checklist_type_id=uuid4(),
        version=1,
        status=ChecklistStatus.published,
        created_by=user.id,
        updated_by=user.id,
    )
    payment = Payment(
        id=uuid4(),
        user_id=user.id,
        checklist_id=checklist.id,
        stripe_payment_intent_id="pi_123",
        amount_cents=4900,
        currency="USD",
        status=PaymentStatus.succeeded,
        paid_at=now - timedelta(minutes=5),
    )
    db.add(user)
    db.add(checklist)
    db.add(payment)

    started = start_assessment(db, user=user, checklist_id=checklist.id)
    assert started.is_new is True
    assert started.status == AssessmentStatus.in_progress

    started_again = start_assessment(db, user=user, checklist_id=checklist.id)
    assert started_again.is_new is False
    assert started_again.assessment_id == started.assessment_id


def test_start_assessment_requires_payment_for_same_checklist() -> None:
    db = FakeSession()
    now = datetime.now(timezone.utc)
    user = User(id=uuid4(), email="u@example.com", password_hash="x", role=UserRole.customer, is_active=True)
    checklist_a = Checklist(
        id=uuid4(),
        checklist_type_id=uuid4(),
        version=1,
        status=ChecklistStatus.published,
        created_by=user.id,
        updated_by=user.id,
    )
    checklist_b = Checklist(
        id=uuid4(),
        checklist_type_id=uuid4(),
        version=1,
        status=ChecklistStatus.published,
        created_by=user.id,
        updated_by=user.id,
    )
    payment_for_a = Payment(
        id=uuid4(),
        user_id=user.id,
        checklist_id=checklist_a.id,
        stripe_payment_intent_id="pi_for_a",
        amount_cents=4900,
        currency="USD",
        status=PaymentStatus.succeeded,
        paid_at=now - timedelta(minutes=5),
    )
    db.add(user)
    db.add(checklist_a)
    db.add(checklist_b)
    db.add(payment_for_a)

    with pytest.raises(HTTPException) as exc:
        start_assessment(db, user=user, checklist_id=checklist_b.id)

    assert exc.value.status_code == 403
    assert exc.value.detail == "payment_required"


def test_get_current_assessment_returns_active() -> None:
    db = FakeSession()
    now = datetime.now(timezone.utc)
    user = User(id=uuid4(), email="u@example.com", password_hash="x", role=UserRole.customer, is_active=True)
    checklist_id = uuid4()
    access_window = AccessWindow(
        id=uuid4(),
        user_id=user.id,
        payment_id=uuid4(),
        activated_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=7),
    )
    assessment = Assessment(
        id=uuid4(),
        user_id=user.id,
        checklist_id=checklist_id,
        access_window_id=access_window.id,
        started_at=now - timedelta(hours=1),
        status=AssessmentStatus.in_progress,
        expires_at=now + timedelta(days=6),
        completion_percent=25,
    )
    db.add(user)
    db.add(access_window)
    db.add(assessment)

    current = get_current_assessment(db, user=user)

    assert current.assessment_id == assessment.id
    assert current.status == AssessmentStatus.in_progress
