from __future__ import annotations

from fastapi import Depends, HTTPException, Header, status

from app.core.config import settings


async def require_admin(x_admin_token: str = Header(default="")) -> None:
    """
    Validates the X-Admin-Token header against the configured secret.

    In a future iteration this can be replaced with Supabase JWT verification:
        token = jwt.decode(x_admin_token, supabase_jwt_secret, algorithms=["HS256"])
        if token.get("role") != "admin": raise HTTPException(403)
    """
    if not settings.n8n_admin_token:
        # If not configured, block all access to prevent accidental exposure
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assistant feature is not configured on this server.",
        )

    if x_admin_token != settings.n8n_admin_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
