"""
Comprehensive i18n (Internationalization) service for multilingual API responses.
Handles language detection, message translation, and content localization.
"""

import logging
from typing import Any, Callable, Dict, Optional
from functools import wraps
from contextlib import contextmanager

from fastapi import Request, HTTPException
from sqlalchemy.orm import Session

from app.models.reference import Language
from app.utils.i18n_messages import translate

logger = logging.getLogger(__name__)

# Thread-local storage for current language context
import threading
_language_context: threading.local = threading.local()


class LanguageContext:
    """
    Thread-safe language context manager for tracking current language in request.
    """
    
    def __init__(self, lang_code: str = "cs"):
        self.lang_code = lang_code
    
    def __enter__(self):
        _language_context.lang_code = self.lang_code
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(_language_context, 'lang_code'):
            delattr(_language_context, 'lang_code')


def get_current_language() -> str:
    """Get current language code from context."""
    return getattr(_language_context, 'lang_code', 'cs')


def set_current_language(lang_code: str) -> None:
    """Set current language code in context."""
    _language_context.lang_code = lang_code


class I18nService:
    """
    Centralized i18n service for handling multilingual API responses.
    
    Features:
    - Automatic language detection from Accept-Language header
    - Fallback to default language if requested language unavailable
    - Message translation with key-based system
    - Content localization support
    - Error message translation
    """
    
    DEFAULT_LANGUAGE = "cs"
    SUPPORTED_LANGUAGES = ["en", "cs"]  # English, Czech (add more as needed)
    
    def __init__(self):
        self._language_cache: Dict[str, Language] = {}
    
    def detect_language(self, request: Optional[Request], db: Session) -> str:
        """
        Detect language from request headers or database default.
        
        Priority:
        1. Accept-Language header
        2. Language query parameter
        3. Default language from database
        4. Fallback to 'en'
        """
        lang_code = self.DEFAULT_LANGUAGE
        
        # Try Accept-Language header
        if request:
            # Check query parameter first
            if hasattr(request, 'query_params') and 'lang' in request.query_params:
                lang_code = request.query_params.get('lang', '').lower()
            
            # Check Accept-Language header
            elif 'accept-language' in request.headers:
                accept_language = request.headers.get('accept-language', '')
                lang_code = accept_language.split(',')[0].split('-')[0].lower()
        
        # Validate language is supported
        if lang_code not in self.SUPPORTED_LANGUAGES:
            # Try to find in database
            lang = db.query(Language).filter(
                Language.code == lang_code,
                Language.is_active == True
            ).first()
            
            if not lang:
                # Fall back to default
                lang = db.query(Language).filter(
                    Language.is_default == True,
                    Language.is_active == True
                ).first()
                lang_code = lang.code if lang else self.DEFAULT_LANGUAGE
            else:
                lang_code = lang.code
        
        return lang_code
    
    def get_message(self, key: str, lang_code: Optional[str] = None, **kwargs) -> str:
        """
        Get translated message by key.
        
        Args:
            key: Message key (e.g., 'checklist_not_found')
            lang_code: Language code (uses current context if not provided)
            **kwargs: String format variables
        
        Returns:
            Translated message or key if not found
        """
        if lang_code is None:
            lang_code = get_current_language()
        
        message = translate(key, lang_code)
        
        # Support string formatting
        try:
            if kwargs:
                message = message.format(**kwargs)
        except (KeyError, ValueError) as e:
            logger.warning(f"Error formatting message '{key}': {e}")
        
        return message
    
    def success_response(
        self,
        data: Any = None,
        message: Optional[str] = None,
        lang_code: Optional[str] = None,
        **meta
    ) -> Dict[str, Any]:
        """
        Build standardized success response.
        
        Example:
            return i18n.success_response(
                data={"id": 123, "name": "Test"},
                message="Created successfully"
            )
        
        Returns:
            {
                "status": "success",
                "lang": "en",
                "data": {...},
                "message": "Created successfully",
                "meta": {...}
            }
        """
        if lang_code is None:
            lang_code = get_current_language()
        
        return {
            "status": "success",
            "lang": lang_code,
            "data": data,
            "message": message,
            "meta": meta or {}
        }
    
    def error_response(
        self,
        error_key: str,
        status_code: int = 400,
        lang_code: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Build standardized error response with translated message.
        
        Example:
            return i18n.error_response(
                error_key="checklist_not_found",
                status_code=404
            )
        
        Returns:
            {
                "status": "error",
                "lang": "en",
                "error": "checklist_not_found",
                "message": "Checklist not found.",
                "status_code": 404,
                "meta": {}
            }
        """
        if lang_code is None:
            lang_code = get_current_language()
        
        message = self.get_message(error_key, lang_code, **kwargs)
        
        return {
            "status": "error",
            "lang": lang_code,
            "error": error_key,
            "message": message,
            "status_code": status_code,
            "meta": {}
        }
    
    def paginated_response(
        self,
        items: list,
        total: int,
        page: int,
        page_size: int,
        lang_code: Optional[str] = None,
        message: Optional[str] = None,
        **meta
    ) -> Dict[str, Any]:
        """
        Build standardized paginated response.
        
        Example:
            return i18n.paginated_response(
                items=checklists,
                total=100,
                page=1,
                page_size=20
            )
        """
        if lang_code is None:
            lang_code = get_current_language()
        
        return {
            "status": "success",
            "lang": lang_code,
            "data": items,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
            },
            "message": message,
            "meta": meta or {}
        }
    
    def validation_error_response(
        self,
        errors: Dict[str, Any],
        message: str = "Validation error",
        lang_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build standardized validation error response.
        
        Example:
            return i18n.validation_error_response(
                errors={"email": "Invalid email format"}
            )
        """
        if lang_code is None:
            lang_code = get_current_language()
        
        return {
            "status": "error",
            "lang": lang_code,
            "error": "validation_error",
            "message": message,
            "status_code": 422,
            "errors": errors,
            "meta": {}
        }
    
    def list_supported_languages(self, db: Session) -> list[Dict[str, Any]]:
        """Get list of all supported/active languages."""
        languages = db.query(Language).filter(Language.is_active == True).all()
        return [
            {
                "code": lang.code,
                "name": lang.name,
                "is_default": lang.is_default
            }
            for lang in languages
        ]
    
    def set_default_language(self, lang_code: str, db: Session) -> bool:
        """Set default language (admin only)."""
        # Reset all to non-default
        db.query(Language).update({Language.is_default: False})
        
        # Set new default
        lang = db.query(Language).filter(Language.code == lang_code).first()
        if lang:
            lang.is_default = True
            db.commit()
            return True
        
        return False


# Global i18n service instance
i18n = I18nService()


def translate_message(
    message_key: str,
    status_code: int = 400,
    lang_code: Optional[str] = None,
) -> tuple[Dict[str, Any], int]:
    """
    Convenience function to translate error message to response.
    
    Usage:
        if not checklist:
            response, code = translate_message("checklist_not_found", 404)
            raise HTTPException(status_code=code, detail=response)
    """
    response = i18n.error_response(message_key, status_code, lang_code)
    return response, status_code


def require_language(
    supported_languages: Optional[list[str]] = None
) -> Callable:
    """
    Decorator to enforce language support on endpoints.
    
    Usage:
        @router.get("/data")
        @require_language(supported_languages=["en", "cs"])
        async def get_data(lang: str = Query("en")):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            lang = kwargs.get('lang', get_current_language())
            
            if supported_languages and lang not in supported_languages:
                raise HTTPException(
                    status_code=400,
                    detail=f"Language '{lang}' not supported. Supported: {', '.join(supported_languages)}"
                )
            
            with LanguageContext(lang):
                return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def i18n_endpoint(lang_code: Optional[str] = None) -> Callable:
    """
    Decorator to automatically handle i18n context for endpoints.
    
    Usage:
        @router.get("/checklists")
        @i18n_endpoint()
        async def get_checklists(request: Request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, request: Optional[Request] = None, db: Optional[Session] = None, **kwargs):
            # Detect language
            detected_lang = i18n.detect_language(request, db) if db else get_current_language()
            
            # Set context
            with LanguageContext(detected_lang):
                return await func(*args, request=request, db=db, **kwargs)
        
        return wrapper
    
    return decorator
