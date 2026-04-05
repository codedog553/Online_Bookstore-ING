from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict

from sqlalchemy.orm import sessionmaker

from .config import Settings
from .logging_config import configure_audit_logger, configure_runtime_logger
from .services.conversations import ConversationStore
from .services.deepseek import DeepSeekService
from .services.rate_limit import SlidingWindowRateLimiter
from .services.skills import SkillRegistry


@dataclass
class Container:
    settings: Settings
    read_sessionmaker: sessionmaker
    write_sessionmaker: sessionmaker
    deepseek: DeepSeekService
    conversations: ConversationStore
    rate_limiter: SlidingWindowRateLimiter
    skills: SkillRegistry
    audit_logger: logging.Logger
    runtime_logger: logging.Logger
    locks: Dict[str, asyncio.Lock]


def build_container(settings: Settings, read_sessionmaker: sessionmaker, write_sessionmaker: sessionmaker) -> Container:
    return Container(
        settings=settings,
        read_sessionmaker=read_sessionmaker,
        write_sessionmaker=write_sessionmaker,
        deepseek=DeepSeekService(settings),
        conversations=ConversationStore(),
        rate_limiter=SlidingWindowRateLimiter(),
        skills=SkillRegistry(),
        audit_logger=configure_audit_logger(settings.log_file),
        runtime_logger=configure_runtime_logger(),
        locks={},
    )


def get_lock(container: Container, key: str) -> asyncio.Lock:
    if key not in container.locks:
        container.locks[key] = asyncio.Lock()
    return container.locks[key]
