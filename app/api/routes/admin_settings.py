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
from app.services.settings_manager import localize_setting_description
from app.utils.i18n_messages import translate


router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


def _request_language(request: Request) -> str:
    lang_code = request.query_params.get("lang") or request.headers.get("accept-language", "")
    lang_code = lang_code.split(",")[0].split("-")[0].lower()
    if lang_code == "cz":
        lang_code = "cs"
    return lang_code if lang_code in {"cs", "en"} else "cs"


def _assert_admin(current_user: User, lang_code: str) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("admin_only", lang_code))


@router.get("", response_model=SystemSettingListResponse)
def list_settings(
    request: Request,
    category: str | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    lang_code = _request_language(request)
    _assert_admin(current_user, lang_code)

    query = db.query(SystemSetting).filter(SystemSetting.is_secret.is_(False))
    if category:
        query = query.filter(SystemSetting.category == category)
    settings = query.order_by(SystemSetting.category.asc(), SystemSetting.key.asc()).all()

    localized_settings = []
    for item in settings:
        setting = SystemSettingResponse.model_validate(item)
        setting.description = localize_setting_description(setting.description, lang_code)
        localized_settings.append(setting)

    return {
        "total": len(settings),
        "categories": sorted({item.category for item in settings}),
        "settings": localized_settings,
    }


@router.patch("/{setting_key}", response_model=SystemSettingResponse)
def update_setting(
    setting_key: str,
    payload: SystemSettingUpdateRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> SystemSettingResponse:
    lang_code = _request_language(request)
    _assert_admin(current_user, lang_code)

    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == setting_key))
    if setting is None or setting.is_secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("setting_not_found", lang_code))
    if setting.is_locked:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("setting_is_locked", lang_code))

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
    response = SystemSettingResponse.model_validate(setting)
    response.description = localize_setting_description(response.description, lang_code)
    return response
