from fastapi import Request
from sqlalchemy.orm import Session
from app.models.reference import Language

DEFAULT_LANGUAGE_CODE = "cs"

def get_language_code(request: Request, db: Session) -> str:
    # Explicit query parameter wins: ?lang=cs or ?lang=en
    lang_code = request.query_params.get("lang")
    if lang_code:
        lang_code = lang_code.split(",")[0].split("-")[0].lower()

    # Fallback to Accept-Language header
    if not lang_code:
        accept_language = request.headers.get("accept-language")
        if accept_language:
            lang_code = accept_language.split(",")[0].split("-")[0].lower()

    # Normalize Czech aliases
    if lang_code == "cz":
        lang_code = "cs"

    if lang_code:
        lang = db.scalar(
            db.query(Language).filter(Language.code == lang_code, Language.is_active == True)
        )
        if lang:
            return lang.code

    # Fallback to default
    lang = db.scalar(db.query(Language).filter(Language.is_default == True, Language.is_active == True))
    return lang.code if lang else DEFAULT_LANGUAGE_CODE
