from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_admin_api_key(x_admin_api_key: str | None = Header(default=None)) -> None:
    if not settings.admin_api_key or settings.admin_api_key == 'change-me':
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='ADMIN_API_KEY is not configured',
        )

    if x_admin_api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid admin API key',
        )
