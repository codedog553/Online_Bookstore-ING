from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from .config import Settings


def decode_user_from_request(request: Request, settings: Settings) -> Optional[Dict[str, Any]]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    return payload


def require_user_id(request: Request, settings: Settings) -> int:
    payload = decode_user_from_request(request, settings)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证")
    try:
        return int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效令牌")


def _encode(payload: Dict[str, Any], secret: str) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def _decode(token: str, secret: str) -> Dict[str, Any]:
    return jwt.decode(token, secret, algorithms=["HS256"])


def issue_confirmation_token(settings: Settings, user_id: int, action: str, payload: Dict[str, Any]) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    body = {"sub": str(user_id), "act": action, "payload": payload, "exp": expires_at}
    return _encode(body, settings.confirmation_secret)


def verify_confirmation_token(settings: Settings, token: str, user_id: int, action: str, payload: Dict[str, Any]) -> None:
    try:
        decoded = _decode(token, settings.confirmation_secret)
    except JWTError:
        raise HTTPException(status_code=400, detail="确认令牌无效或已过期")
    if str(decoded.get("sub")) != str(user_id) or decoded.get("act") != action or decoded.get("payload") != payload:
        raise HTTPException(status_code=400, detail="确认令牌与请求不匹配")


def issue_csrf_token(settings: Settings, user_id: Optional[int]) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    body = {"sub": str(user_id or 0), "kind": "csrf", "exp": expires_at}
    return _encode(body, settings.csrf_secret)


def verify_csrf(request: Request, settings: Settings, user_id: Optional[int]) -> None:
    header_token = request.headers.get("X-CSRF-Token")
    cookie_token = request.cookies.get("agent_csrf")
    if not header_token or not cookie_token or header_token != cookie_token:
        raise HTTPException(status_code=403, detail="CSRF 校验失败")
    try:
        decoded = _decode(header_token, settings.csrf_secret)
    except JWTError:
        raise HTTPException(status_code=403, detail="CSRF 令牌无效")
    if decoded.get("kind") != "csrf" or str(decoded.get("sub")) != str(user_id or 0):
        raise HTTPException(status_code=403, detail="CSRF 令牌无效")
