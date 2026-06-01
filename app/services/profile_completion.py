from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import ProfileCompletionItem, ProfileCompletionResponse


def build_profile_completion(user: User, db: Session) -> ProfileCompletionResponse:
    from app.models.company import Company

    company = None
    if user.primary_company_id:
        company = db.query(Company).filter(Company.id == user.primary_company_id).first()

    personal_complete = all(
        bool((value or "").strip())
        for value in [user.full_name, user.username, user.job_title, user.department]
    )

    company_complete = bool(
        company
        and (company.name or "").strip()
        and (company.slug or "").strip()
        and (company.industry or "").strip()
        and (company.size or "").strip()
        and (company.region or "").strip()
        and (company.country or "").strip()
        and (company.website or "").strip()
    )

    mfa_record = getattr(user, "mfa_totp", None)
    mfa_complete = bool(mfa_record and mfa_record.is_verified)
    email_verified_complete = bool(user.email_verified)

    notification_complete = all(
        value is not None
        for value in [
            user.email_notifications_enabled,
            user.email_pref_reports_alert,
            user.email_pref_payment_success_alert,
            user.email_pref_assessment_submitted,
            user.email_pref_assessment_started,
        ]
    )

    billing_complete = bool(
        company
        and (company.billing_contact_name or "").strip()
        and (company.billing_email or "").strip()
        and (company.billing_address_line1 or "").strip()
        and (company.billing_city or "").strip()
        and (company.billing_postal_code or "").strip()
        and (company.billing_country or "").strip()
    )

    checks: list[ProfileCompletionItem] = [
        ProfileCompletionItem(section="profile", field="personal_details", label="Personal details completion", completed=personal_complete),
        ProfileCompletionItem(section="company", field="organizational_company_details", label="Organizational/company details completion", completed=company_complete),
        ProfileCompletionItem(section="security", field="email_verified", label="Email verification completion", completed=email_verified_complete),
        ProfileCompletionItem(section="security", field="mfa_setup", label="MFA setup completion", completed=mfa_complete),
        ProfileCompletionItem(section="preferences", field="notification_preferences", label="Notification preference configuration completion", completed=notification_complete),
        ProfileCompletionItem(section="billing", field="billing_details", label="Billing details completion", completed=billing_complete),
    ]

    completed_fields = [item for item in checks if item.completed]
    missing_fields = [item for item in checks if not item.completed]
    total = len(checks)
    completion_percent = round((len(completed_fields) / total) * 100.0, 2) if total else 100.0

    return ProfileCompletionResponse(
        completion_percent=completion_percent,
        is_complete=len(missing_fields) == 0,
        missing_fields=missing_fields,
        completed_fields=completed_fields,
    )