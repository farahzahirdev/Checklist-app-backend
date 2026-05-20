from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system_setting import SystemSetting

logger = logging.getLogger(__name__)


DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    "email_enabled": {
        "value": "false",
        "value_type": "bool",
        "category": "email",
        "description": "Enable outbound notification emails",
    },
    "smtp_host": {
        "value": "smtp.office365.com",
        "value_type": "string",
        "category": "email",
        "description": "SMTP host",
    },
    "smtp_port": {
        "value": "587",
        "value_type": "int",
        "category": "email",
        "description": "SMTP port",
    },
    "smtp_use_tls": {
        "value": "true",
        "value_type": "bool",
        "category": "email",
        "description": "Use TLS for SMTP connection",
    },
    "email_from_address": {
        "value": "noreply@auditready.cz",
        "value_type": "string",
        "category": "email",
        "description": "Email sender address",
    },
    "email_from_name": {
        "value": "AuditReady",
        "value_type": "string",
        "category": "email",
        "description": "Email sender display name",
    },
    "email_reply_to": {
        "value": "support@auditready.cz",
        "value_type": "string",
        "category": "email",
        "description": "Reply-to address for notifications",
    },
    "email_max_retries": {
        "value": "3",
        "value_type": "int",
        "category": "email",
        "description": "Maximum retry attempts for failed emails",
    },
    "email_retry_delay_seconds": {
        "value": "60",
        "value_type": "int",
        "category": "email",
        "description": "Base retry delay in seconds",
    },
    "assessment_completion_days": {
        "value": "7",
        "value_type": "int",
        "category": "lifecycle",
        "description": "Days available to complete an assessment",
    },
    "evidence_retention_hours": {
        "value": "48",
        "value_type": "int",
        "category": "lifecycle",
        "description": "Hours to retain evidence after report publish",
    },
}


def coerce_setting_value(raw_value: str, value_type: str) -> Any:
    if value_type == "int":
        return int(raw_value)
    if value_type == "bool":
        return raw_value.lower() in {"1", "true", "yes", "on"}
    if value_type == "json":
        return json.loads(raw_value)
    return raw_value


def seed_default_settings(db: Session) -> int:
    created = 0
    for key, config in DEFAULT_SETTINGS.items():
        existing = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if existing is not None:
            continue
        db.add(
            SystemSetting(
                key=key,
                value=str(config["value"]),
                value_type=str(config["value_type"]),
                category=str(config["category"]),
                description=config.get("description"),
                is_secret=bool(config.get("is_secret", False)),
                is_locked=bool(config.get("is_locked", False)),
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def get_runtime_setting(db: Session, key: str, default: Any) -> Any:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if setting is None:
        return default
    if setting.value is None:
        return default
    if isinstance(setting.value, str) and setting.value.strip() == "":
        return default
    try:
        return coerce_setting_value(setting.value, setting.value_type)
    except Exception:
        logger.warning("Invalid value for system setting key=%s; using fallback", key)
        return default


def get_runtime_int(db: Session, key: str, default: int) -> int:
    value = get_runtime_setting(db, key, default)
    try:
        return int(value)
    except Exception:
        return default


def get_runtime_bool(db: Session, key: str, default: bool) -> bool:
    value = get_runtime_setting(db, key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def get_runtime_str(db: Session, key: str, default: str) -> str:
    value = get_runtime_setting(db, key, default)
    return str(value) if value is not None else default
