from __future__ import annotations

import html
import re

from fastapi import HTTPException


SCRIPT_PATTERN = re.compile(r"<\s*script|javascript:|onerror\s*=|onload\s*=", re.IGNORECASE)


def validate_safe_text(text: str) -> str:
    value = (text or "").strip()
    if not value:
        raise HTTPException(status_code=422, detail="输入不能为空")
    if SCRIPT_PATTERN.search(value):
        raise HTTPException(status_code=400, detail="输入包含不安全内容")
    return value


def escape_text(text: str) -> str:
    return html.escape(text, quote=True)
