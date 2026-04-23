from fastapi import Request
from sqlalchemy.orm import Session
from app.models.reference import Language

DEFAULT_LANGUAGE_CODE = "en"

def get_language_code(request: Request, db: Session) -> str:
    # Try Accept-Language header
    accept_language = request.headers.get("accept-language")
    if accept_language:
        lang_code = accept_language.split(",")[0].split("-")[0].lower()
        lang = db.scalar(
            db.query(Language).filter(Language.code == lang_code, Language.is_active == True)
        )
        if lang:
            return lang.code
    # Fallback to default
    lang = db.scalar(db.query(Language).filter(Language.is_default == True, Language.is_active == True))
    return lang.code if lang else DEFAULT_LANGUAGE_CODE
