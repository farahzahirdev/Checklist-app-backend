from __future__ import annotations

from app.core.security import hash_password, verify_password
from app.models.user import User
import app.api.routes.user_management as admin_routes


def test_admin_profile_get_and_update(client, db, admin_user):
    admin_user.password_hash = hash_password("OldPass123")
    admin_user.full_name = "Original Name"
    admin_user.username = "original-admin"
    admin_user.job_title = "Security Lead"
    admin_user.department = "Compliance"
    db.commit()

    client.app.dependency_overrides[admin_routes.get_current_user] = lambda: admin_user
    try:
        response = client.get("/api/api/v1/admin/profile")
        assert response.status_code == 200
        profile = response.json()
        assert profile["email"] == admin_user.email
        assert profile["full_name"] == "Original Name"
        assert "company_name" not in profile
        assert "company_slug" not in profile

        update_response = client.patch(
            "/api/api/v1/admin/profile",
            json={
                "full_name": "Updated Admin",
                "username": "updated-admin",
                "job_title": "Head of Compliance",
                "department": "Risk",
            },
        )

        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["full_name"] == "Updated Admin"
        assert updated["username"] == "updated-admin"
        assert "company_name" not in updated

        db.expire_all()
        refreshed = db.get(User, admin_user.id)
        assert refreshed is not None
        assert refreshed.full_name == "Updated Admin"
        assert refreshed.username == "updated-admin"
    finally:
        client.app.dependency_overrides.pop(admin_routes.get_current_user, None)


def test_admin_profile_password_change(client, db, admin_user):
    admin_user.password_hash = hash_password("OldPass123")
    db.commit()

    client.app.dependency_overrides[admin_routes.get_current_user] = lambda: admin_user
    try:
        response = client.patch(
            "/api/api/v1/admin/profile/password",
            json={
                "current_password": "OldPass123",
                "new_password": "NewPass123",
                "confirm_password": "NewPass123",
            },
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Password changed successfully."

        db.expire_all()
        refreshed = db.get(User, admin_user.id)
        assert refreshed is not None
        assert verify_password("NewPass123", refreshed.password_hash)
    finally:
        client.app.dependency_overrides.pop(admin_routes.get_current_user, None)