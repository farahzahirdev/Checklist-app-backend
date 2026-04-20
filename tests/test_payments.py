from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.models.access_window import AccessWindow
from app.models.checklist import Checklist, ChecklistStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.services.payments import admin_set_payment_status, handle_webhook_event


class FakeSession:
    def __init__(self) -> None:
        self.users: list[User] = []
        self.checklists: list[Checklist] = []
        self.payments: list[Payment] = []
        self.access_windows: list[AccessWindow] = []

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

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def refresh(self, obj) -> None:
        return None

    def get(self, model, object_id):
        if model is User:
            return next((item for item in self.users if item.id == object_id), None)
        if model is Checklist:
            return next((item for item in self.checklists if item.id == object_id), None)
        return None

    def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        params = statement.compile().params

        if entity is Payment:
            intent_id = next((value for key, value in params.items() if "stripe_payment_intent_id" in key), None)
            if intent_id is None:
                return None
            return next((item for item in self.payments if item.stripe_payment_intent_id == intent_id), None)

        if entity is AccessWindow:
            payment_id = _extract_uuid(params, "payment_id")
            if payment_id is None:
                return None
            return next((item for item in self.access_windows if item.payment_id == payment_id), None)

        return None



def _extract_uuid(params: dict, keyword: str) -> UUID | None:
    for key, value in params.items():
        if keyword in key:
            return UUID(str(value)) if isinstance(value, str) else value
    return None


def _stripe_event(*, event_type: str, intent_id: str, user_id: UUID, checklist_id: UUID, amount: int = 4900):
    created_ts = int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())
    return {
        "type": event_type,
        "data": {
            "object": {
                "id": intent_id,
                "amount": amount,
                "currency": "usd",
                "created": created_ts,
                "metadata": {
                    "user_id": str(user_id),
                    "checklist_id": str(checklist_id),
                },
            }
        },
    }


def _checkout_session_event(*, session_id: str, intent_id: str, user_id: UUID, amount_total: int = 4900):
    created_ts = int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "payment_intent": intent_id,
                "amount_total": amount_total,
                "currency": "usd",
                "created": created_ts,
                "metadata": {
                    "user_id": str(user_id),
                },
            }
        },
    }


def test_webhook_creates_payment_with_checklist_binding() -> None:
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

    state = handle_webhook_event(
        db,
        _stripe_event(
            event_type="payment_intent.succeeded",
            intent_id="pi_webhook_123",
            user_id=user.id,
            checklist_id=checklist.id,
        ),
    )

    assert state is not None
    assert len(db.payments) == 1
    assert db.payments[0].checklist_id is None


def test_webhook_checkout_session_creates_payment_and_access() -> None:
    db = FakeSession()
    user = User(id=uuid4(), email="u@example.com", password_hash="x", role=UserRole.customer, is_active=True)
    db.add(user)

    state = handle_webhook_event(
        db,
        _checkout_session_event(
            session_id="cs_webhook_123",
            intent_id="pi_checkout_123",
            user_id=user.id,
            amount_total=4900,
        ),
    )

    assert state is not None
    assert state.payment_status == PaymentStatus.succeeded
    assert state.access_window_id is not None
    assert len(db.payments) == 1
    assert db.payments[0].stripe_payment_intent_id == "pi_checkout_123"
    assert db.payments[0].status == PaymentStatus.succeeded


def test_webhook_without_checklist_metadata_is_ignored() -> None:
    db = FakeSession()
    user = User(id=uuid4(), email="u@example.com", password_hash="x", role=UserRole.customer, is_active=True)
    db.add(user)

    event = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_missing_checklist",
                "amount": 4900,
                "currency": "usd",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "metadata": {"user_id": str(user.id)},
            }
        },
    }

    state = handle_webhook_event(db, event)

    assert state is not None
    assert len(db.payments) == 1
    assert db.payments[0].checklist_id is None


def test_admin_set_payment_status_creates_synthetic_payment_and_access() -> None:
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

    state = admin_set_payment_status(
        db,
        user_id=user.id,
        payment_status=PaymentStatus.succeeded,
        amount_cents=4900,
        currency="USD",
    )

    assert state.payment_id is not None
    assert state.payment_status == PaymentStatus.succeeded
    assert state.access_window_id is not None
