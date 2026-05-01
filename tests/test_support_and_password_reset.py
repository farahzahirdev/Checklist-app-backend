from __future__ import annotations

import pytest

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User


@pytest.fixture(scope="function")
def customer_token(customer_user):
    return create_access_token(user_id=str(customer_user.id), role=str(customer_user.role))


def test_admin_can_reset_password(client, db, admin_token, customer_user):
    customer_user.password_hash = hash_password("OldPass123")
    db.commit()

    response = client.post(
        f"/api/api/v1/admin/users/{customer_user.id}/password/reset",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"new_password": "NewPass123", "reason": "Account recovery"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == customer_user.email
    assert data["message"] == "Password reset successfully."

    db.expire_all()
    updated_user = db.get(User, customer_user.id)
    assert updated_user is not None
    assert verify_password("NewPass123", updated_user.password_hash)


def test_support_ticket_thread_flow(client, customer_token, admin_token):
    create_response = client.post(
        "/api/api/v1/customer/support/tickets",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"subject": "Cannot access report", "message": "My report still shows as unavailable."},
    )

    assert create_response.status_code == 200
    ticket = create_response.json()
    ticket_id = ticket["id"]
    assert ticket["customer_email"]

    reply_response = client.post(
        f"/api/api/v1/admin/support/tickets/{ticket_id}/reply",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"message": "We have approved your report. Please refresh the page."},
    )

    assert reply_response.status_code == 200
    reply_data = reply_response.json()
    assert len(reply_data["messages"]) == 2
    assert reply_data["messages"][-1]["sender_role"] == "admin"

    customer_detail = client.get(
        f"/api/api/v1/customer/support/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    assert customer_detail.status_code == 200
    customer_ticket = customer_detail.json()
    assert customer_ticket["messages"][-1]["body"] == "We have approved your report. Please refresh the page."
    assert customer_ticket["status"] == "waiting_customer"
