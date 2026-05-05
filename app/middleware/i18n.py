"""
FastAPI middleware for automatic language detection and context management.
Detects language from request headers/params and sets context for entire request.
"""

import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.session import get_db
from app.services.i18n_service import i18n, set_current_language

logger = logging.getLogger(__name__)


class I18nMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically detect and set language context for each request.
    
    Priority for language detection:
    1. Query parameter: ?lang=cs
    2. Accept-Language header: Accept-Language: cs-CZ
    3. Database default language
    4. Fallback to 'en'
    
    Usage in main.py:
        from app.middleware.i18n import I18nMiddleware
        
        app.add_middleware(I18nMiddleware)
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> any:
        """
        Detect language and set context before processing request.
        """
        try:
            # Get database session for language detection
            db_session = next(get_db())
            
            # Detect language from request
            lang_code = i18n.detect_language(request, db_session)
            
            # Set language context for this request
            set_current_language(lang_code)
            
            # Add language to response headers
            response = await call_next(request)
            response.headers["Content-Language"] = lang_code
            response.headers["X-Request-Language"] = lang_code
            
            return response
        
        except Exception as e:
            logger.warning(f"Error in I18nMiddleware: {e}, using default language")
            # Fall back to default language
            set_current_language("en")
            return await call_next(request)
        
        finally:
            # Clean up database session
            try:
                db_session.close()
            except:
                pass
