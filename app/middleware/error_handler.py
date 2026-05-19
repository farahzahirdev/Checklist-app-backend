"""
Global error handling middleware for FastAPI application.
Catches and properly formats all exceptions with user-friendly messages.
"""

import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.i18n_service import get_current_language
from app.utils.i18n_messages import translate

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle all exceptions and format error responses.
    Handles:
    - 413 Payload Too Large
    - 500 Internal Server Errors
    - 502 Bad Gateway
    - 503 Service Unavailable
    """

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        try:
            response = await call_next(request)
            
            # Handle HTTP response codes that indicate errors
            if response.status_code in [413, 500, 502, 503]:
                return self._handle_error_response(response.status_code)
            
            return response
        
        except StarletteHTTPException:
            # Let HTTPException be handled by the exception handler in main.py
            raise
        
        except Exception as exc:
            logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
            return self._handle_error_response(500)
    
    def _handle_error_response(self, status_code: int) -> JSONResponse:
        """Convert error codes to user-friendly messages."""
        try:
            lang_code = get_current_language()
        except:
            lang_code = "en"
        
        # Map status codes to message keys
        message_map = {
            413: "request_too_large",
            500: "internal_server_error",
            502: "bad_gateway",
            503: "service_unavailable",
        }
        
        message_key = message_map.get(status_code, "server_error")
        translated_message = translate(message_key, lang_code)
        
        return JSONResponse(
            status_code=status_code,
            content={"detail": translated_message}
        )


class PayloadTooLargeMiddleware(BaseHTTPMiddleware):
    """
    Specific middleware to catch and handle 413 Payload Too Large errors
    that occur during request parsing (before route handlers).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Check if this is a payload too large error
            error_str = str(exc).lower()
            if any(keyword in error_str for keyword in ["payload", "large", "size", "413", "content-length"]):
                logger.warning(f"Payload too large error: {str(exc)}")
                try:
                    lang_code = get_current_language()
                except:
                    lang_code = "en"
                
                message = translate("request_too_large", lang_code)
                return JSONResponse(
                    status_code=413,
                    content={"detail": message}
                )
            
            # Re-raise other exceptions
            raise
