"""
I18n (Internationalization) administration and management endpoints.
Provides endpoints for managing languages, translations, and language settings.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_admin_only
from app.db.session import get_db
from app.models.reference import Language
from app.services.i18n_service import i18n

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/i18n", tags=["admin-i18n"], dependencies=[Depends(require_admin_only())])


@router.get("/languages")
async def list_languages(db: Session = Depends(get_db)):
    """
    Get list of all supported/active languages.
    
    Returns:
        {
            "status": "success",
            "data": [
                {"code": "en", "name": "English", "is_default": true},
                {"code": "cs", "name": "Czech", "is_default": false}
            ]
        }
    """
    languages = i18n.list_supported_languages(db)
    return i18n.success_response(data=languages, message="Languages retrieved successfully")


@router.get("/languages/{lang_code}")
async def get_language_details(
    lang_code: str,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific language."""
    lang = db.query(Language).filter(Language.code == lang_code).first()
    
    if not lang:
        response, status_code = i18n.error_response("language_not_found", 404, lang_code=lang_code)
        raise HTTPException(status_code=status_code, detail=response)
    
    return i18n.success_response(
        data={
            "code": lang.code,
            "name": lang.name,
            "is_default": lang.is_default,
            "is_active": lang.is_active,
            "created_at": lang.created_at,
            "updated_at": lang.updated_at,
        },
        message="Language details retrieved"
    )


@router.post("/languages")
async def create_language(
    code: str = Query(..., min_length=2, max_length=10),
    name: str = Query(..., min_length=1, max_length=80),
    is_default: bool = Query(False),
    is_active: bool = Query(True),
    db: Session = Depends(get_db),
):
    """
    Create a new language.
    
    Query Parameters:
        - code: Language code (e.g., 'en', 'cs', 'fr')
        - name: Language name (e.g., 'English', 'Czech')
        - is_default: Make this the default language
        - is_active: Language is active/available
    """
    # Check if language already exists
    existing = db.query(Language).filter(Language.code == code).first()
    if existing:
        response, status_code = i18n.error_response(
            "language_code_already_exists",
            409,
            code=code
        )
        raise HTTPException(status_code=status_code, detail=response)
    
    # If making default, unset other defaults
    if is_default:
        db.query(Language).update({Language.is_default: False})
    
    # Create language
    lang = Language(code=code, name=name, is_default=is_default, is_active=is_active)
    db.add(lang)
    db.commit()
    
    logger.info(f"Created language: {code} ({name})")
    
    return i18n.success_response(
        data={"code": lang.code, "name": lang.name},
        message="Language created successfully"
    )


@router.put("/languages/{lang_code}")
async def update_language(
    lang_code: str,
    name: Optional[str] = Query(None, max_length=80),
    is_default: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Update language properties.
    
    Path Parameters:
        - lang_code: Language code to update
    
    Query Parameters:
        - name: New language name
        - is_default: Set as default language
        - is_active: Activate/deactivate language
    """
    lang = db.query(Language).filter(Language.code == lang_code).first()
    
    if not lang:
        response, status_code = i18n.error_response("language_not_found", 404)
        raise HTTPException(status_code=status_code, detail=response)
    
    # Update fields
    if name is not None:
        lang.name = name
    
    if is_default is not None and is_default:
        # Unset other defaults
        db.query(Language).update({Language.is_default: False})
        lang.is_default = True
    
    if is_active is not None:
        lang.is_active = is_active
    
    db.commit()
    
    logger.info(f"Updated language: {lang_code}")
    
    return i18n.success_response(
        data={"code": lang.code, "name": lang.name, "is_default": lang.is_default},
        message="Language updated successfully"
    )


@router.post("/languages/{lang_code}/set-default")
async def set_default_language(
    lang_code: str,
    db: Session = Depends(get_db),
):
    """Set a language as the default language for the system."""
    result = i18n.set_default_language(lang_code, db)
    
    if not result:
        response, status_code = i18n.error_response("language_not_found", 404)
        raise HTTPException(status_code=status_code, detail=response)
    
    logger.info(f"Set default language: {lang_code}")
    
    return i18n.success_response(
        message=f"Language '{lang_code}' is now the default"
    )


@router.get("/translations/{message_key}")
async def get_message_translations(
    message_key: str,
    lang_code: Optional[str] = Query(None),
):
    """
    Get all translations for a message key.
    
    Returns translations in all supported languages.
    
    Example: GET /admin/i18n/translations/checklist_not_found
    
    Returns:
        {
            "status": "success",
            "data": {
                "en": "Checklist not found.",
                "cs": "Kontrolní seznam nebyl nalezen."
            }
        }
    """
    translations = {}
    
    for supported_lang in i18n.SUPPORTED_LANGUAGES:
        message = i18n.get_message(message_key, supported_lang)
        translations[supported_lang] = message
    
    return i18n.success_response(
        data={
            "key": message_key,
            "translations": translations
        },
        message="Message translations retrieved"
    )


@router.get("/check-translation/{message_key}")
async def check_message_translation(
    message_key: str,
    lang_code: Optional[str] = Query("en"),
):
    """
    Check if a message key is translated for a specific language.
    
    Returns the translated message and metadata.
    """
    message = i18n.get_message(message_key, lang_code)
    
    return i18n.success_response(
        data={
            "key": message_key,
            "lang_code": lang_code,
            "message": message,
            "is_translated": message != message_key,  # If translation exists, message != key
        },
        message="Translation checked"
    )


@router.get("/stats")
async def get_i18n_stats(db: Session = Depends(get_db)):
    """Get internationalization statistics."""
    languages = db.query(Language).all()
    
    return i18n.success_response(
        data={
            "total_languages": len(languages),
            "active_languages": len([l for l in languages if l.is_active]),
            "default_language": next((l.code for l in languages if l.is_default), None),
            "supported_languages": i18n.SUPPORTED_LANGUAGES,
            "languages": [
                {
                    "code": l.code,
                    "name": l.name,
                    "is_default": l.is_default,
                    "is_active": l.is_active
                }
                for l in languages
            ]
        },
        message="I18n statistics retrieved"
    )
