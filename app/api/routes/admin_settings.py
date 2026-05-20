from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.audit_log import AuditAction, AuditLog
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.schemas.system_setting import (
    SystemSettingListResponse,
    SystemSettingResponse,
    SystemSettingUpdateRequest,
)


router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


def _assert_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


@router.get("", response_model=SystemSettingListResponse)
def list_settings(
    request: Request,
    category: str | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    _assert_admin(current_user)

    query = db.query(SystemSetting).filter(SystemSetting.is_secret.is_(False))
    if category:
        query = query.filter(SystemSetting.category == category)
    settings = query.order_by(SystemSetting.category.asc(), SystemSetting.key.asc()).all()

    return {
        "total": len(settings),
        "categories": sorted({item.category for item in settings}),
        "settings": [SystemSettingResponse.model_validate(item) for item in settings],
    }


@router.patch("/{setting_key}", response_model=SystemSettingResponse)
def update_setting(
    setting_key: str,
    payload: SystemSettingUpdateRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> SystemSettingResponse:
    _assert_admin(current_user)

    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == setting_key))
    if setting is None or setting.is_secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    if setting.is_locked:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Setting is locked")

    before_value = setting.value
    setting.value = payload.value

    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            actor_role=str(current_user.role),
            action=AuditAction.settings_change,
            target_entity="system_setting",
            target_id=setting.id,
            target_user_id=None,
            changes_summary=payload.reason or f"Updated {setting.key}",
            before_json={"value": before_value},
            after_json={"value": setting.value},
            success=True,
        )
    )

    db.add(setting)
    db.commit()
    db.refresh(setting)
    return SystemSettingResponse.model_validate(setting)
