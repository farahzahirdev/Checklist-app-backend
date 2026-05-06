from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import verify_signed_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.rbac import RBACService
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    lang_code = get_language_code(request, db)
    
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=translate("missing_bearer_token", lang_code))

    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=translate("missing_bearer_token", lang_code))

    try:
        claims = verify_signed_token(token)
    except HTTPException as exc:
        # Translate the detail from security module
        exc.detail = translate(exc.detail, lang_code)
        raise exc

    try:
        user_id = UUID(str(claims.get("sub", "")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=translate("invalid_token_subject", lang_code)) from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=translate("user_not_found", lang_code))

    return user


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    def dependency(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        lang_code = get_language_code(request, db)
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("insufficient_permissions", lang_code))
        return current_user

    return dependency


def require_permission(resource: str, action: str) -> Callable[[User], User]:
    """
    Require a specific RBAC permission.
    
    Args:
        resource: Permission resource (e.g., 'checklist_admin', 'user_management')
        action: Permission action (e.g., 'read', 'manage', 'create')
    
    Returns:
        Dependency function that checks permission
    """
    def dependency(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        lang_code = get_language_code(request, db)
        if not RBACService.has_permission(db, current_user.id, resource, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("insufficient_permissions", lang_code))
        return current_user

    return dependency


def require_admin_or_auditor_for_read() -> Callable[[User], User]:
    """
    Allow admin or auditor roles for read-only operations.
    This provides backward compatibility while transitioning to RBAC.
    """
    def dependency(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        lang_code = get_language_code(request, db)
        if current_user.role not in [UserRole.admin, UserRole.auditor]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("insufficient_permissions", lang_code))
        return current_user

    return dependency


def require_admin_only() -> Callable[[User], User]:
    """
    Require admin role only for write operations.
    """
    def dependency(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        lang_code = get_language_code(request, db)
        if current_user.role != UserRole.admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("insufficient_permissions", lang_code))
        return current_user

    return dependency