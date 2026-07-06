import logging
from fastapi import Request
from sqlalchemy.orm import Session
from app.models.reference import Language
from app.models.user import User

logger = logging.getLogger(__name__)
DEFAULT_LANGUAGE_CODE = "cs"

def get_language_code(request: Request, db: Session, current_user: User | None = None) -> str:
    def _normalize(raw: str | None) -> str | None:
        if not raw:
            return None
        lang_code = raw.split(",")[0].split("-")[0].lower()
        if lang_code == "cz":
            lang_code = "cs"
        if lang_code in {"cs", "en"}:
            return lang_code
        lang = db.scalar(
            db.query(Language).filter(Language.code == lang_code, Language.is_active == True)
        )
        return lang.code if lang else None

    # 1) Explicit query parameter (?lang=en)
    query_lang = _normalize(request.query_params.get("lang"))
    if query_lang:
        logger.info(f"Returning language from query parameter: {query_lang}")
        return query_lang

    # 2) UI locale from Accept-Language (frontend stores checklist_locale)
    header_lang = _normalize(request.headers.get("accept-language"))
    if header_lang:
        logger.info(f"Returning language from Accept-Language header: {header_lang}")
        return header_lang

    # 3) Stored account preference
    if current_user and getattr(current_user, "preferred_language", None):
        user_lang = _normalize(current_user.preferred_language)
        if user_lang:
            logger.info(f"Returning language from user preference: {user_lang}")
            return user_lang

    # 4) Default language row or Czech fallback
    lang = db.scalar(db.query(Language).filter(Language.is_default == True, Language.is_active == True))
    result = lang.code if lang else DEFAULT_LANGUAGE_CODE
    logger.info(f"Returning default language: {result}")
    return result
