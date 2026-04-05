from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def build_sessionmaker(url: str):
    engine = create_engine(url, connect_args=_connect_args(url), future=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
