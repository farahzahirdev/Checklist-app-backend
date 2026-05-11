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
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")

    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")

    claims = verify_signed_token(token)

    try:
        user_id = UUID(str(claims.get("sub", "")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_subject") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")

    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Get current user if authenticated, otherwise return None (no error)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    token = credentials.credentials.strip()
    if not token:
        return None

    try:
        claims = verify_signed_token(token)
        user_id = UUID(str(claims.get("sub", "")))
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return None
        return user
    except Exception:
        # Any error in token verification returns None instead of raising
        return None


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_permissions")
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