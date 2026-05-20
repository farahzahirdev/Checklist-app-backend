from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system_setting import SystemSetting

logger = logging.getLogger(__name__)


def _localized_text(czech: str, english: str) -> dict[str, str]:
    return {"cs": czech, "en": english}


def _serialize_description(description: Any) -> str | None:
    if description is None:
        return None
    if isinstance(description, str):
        return description
    return json.dumps(description, ensure_ascii=False)


def localize_setting_description(description: str | None, lang_code: str) -> str | None:
    if description is None:
        return None

    try:
        parsed = json.loads(description)
    except Exception:
        return description

    if not isinstance(parsed, dict):
        return description

    lang = (lang_code or "en").lower()
    if lang == "cz":
        lang = "cs"
    value = parsed.get(lang) or parsed.get("en") or parsed.get("cs")
    if isinstance(value, str) and value.strip():
        return value
    return description


DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    "email_enabled": {
        "value": "false",
        "value_type": "bool",
        "category": "email",
        "description": _localized_text("Povolit odchozí e-mailová upozornění", "Enable outbound notification emails"),
    },
    "email_provider": {
        "value": "smtp",
        "value_type": "string",
        "category": "email",
        "description": _localized_text("Poskytovatel e-mailu (smtp nebo graph)", "Email provider to use: 'smtp' for SMTP, 'graph' for Microsoft Graph OAuth"),
    },
    "smtp_host": {
        "value": "smtp.office365.com",
        "value_type": "string",
        "category": "email",
        "description": _localized_text("SMTP hostitel", "SMTP host"),
    },
    "smtp_port": {
        "value": "587",
        "value_type": "int",
        "category": "email",
        "description": _localized_text("SMTP port", "SMTP port"),
    },
    "smtp_use_tls": {
        "value": "true",
        "value_type": "bool",
        "category": "email",
        "description": _localized_text("Použít TLS pro SMTP připojení", "Use TLS for SMTP connection"),
    },
    "email_from_address": {
        "value": "noreply@auditready.cz",
        "value_type": "string",
        "category": "email",
        "description": _localized_text("E-mailová adresa odesílatele", "Email sender address"),
    },
    "email_from_name": {
        "value": "AuditReady",
        "value_type": "string",
        "category": "email",
        "description": _localized_text("Zobrazované jméno odesílatele", "Email sender display name"),
    },
    "email_reply_to": {
        "value": "support@auditready.cz",
        "value_type": "string",
        "category": "email",
        "description": _localized_text("Adresa pro odpověď na oznámení", "Reply-to address for notifications"),
    },
    "email_max_retries": {
        "value": "3",
        "value_type": "int",
        "category": "email",
        "description": _localized_text("Maximální počet pokusů o opakování neúspěšného e-mailu", "Maximum retry attempts for failed emails"),
    },
    "email_retry_delay_seconds": {
        "value": "60",
        "value_type": "int",
        "category": "email",
        "description": _localized_text("Základní prodleva opakování v sekundách", "Base retry delay in seconds"),
    },
    # Microsoft Graph OAuth fields for email
    "graph_client_id": {
        "value": "",
        "value_type": "string",
        "category": "email",
        "description": _localized_text("Microsoft Graph Client ID", "Microsoft Graph Client ID for OAuth app registration"),
    },
    "graph_client_secret": {
        "value": "",
        "value_type": "string",
        "category": "email",
        "description": _localized_text("Microsoft Graph Client Secret", "Microsoft Graph Client Secret for OAuth app registration"),
        "is_secret": True,
    },
    "graph_tenant_id": {
        "value": "",
        "value_type": "string",
        "category": "email",
        "description": _localized_text("Microsoft Tenant ID", "Microsoft 365 Tenant ID for Graph API"),
    },
    "graph_mailbox": {
        "value": "",
        "value_type": "string",
        "category": "email",
        "description": _localized_text("Graph Mailbox Address", "Email address of the shared mailbox to send from (e.g. info@auditready.cz)"),
    },
    "graph_redirect_uri": {
        "value": "",
        "value_type": "string",
        "category": "email",
        "description": _localized_text("OAuth Redirect URI", "Redirect URI for Microsoft Graph OAuth app"),
    },
    "graph_refresh_token": {
        "value": "",
        "value_type": "string",
        "category": "email",
        "description": _localized_text("Graph Refresh Token", "Refresh token for Microsoft Graph API access (set after admin consent)"),
        "is_secret": True,
    },
    "assessment_completion_days": {
        "value": "7",
        "value_type": "int",
        "category": "lifecycle",
        "description": _localized_text("Počet dní dostupných pro dokončení hodnocení", "Days available to complete an assessment"),
    },
    "evidence_retention_hours": {
        "value": "48",
        "value_type": "int",
        "category": "lifecycle",
        "description": _localized_text("Počet hodin uchování důkazů po zveřejnění zprávy", "Hours to retain evidence after report publish"),
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
                description=_serialize_description(config.get("description")),
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
