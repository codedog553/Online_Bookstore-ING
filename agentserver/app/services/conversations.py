from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Deque, Dict, List, Optional, Tuple
from uuid import uuid4


ConversationEntry = Tuple[str, str, datetime]


class ConversationStore:
    def __init__(self, ttl_minutes: int = 30, max_messages: int = 12) -> None:
        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_messages = max_messages
        self._store: Dict[str, Deque[ConversationEntry]] = defaultdict(deque)
        self._owners: Dict[str, str] = {}

    def get_or_create_id(self, conversation_id: str | None) -> str:
        return conversation_id or uuid4().hex

    def bind_owner(self, conversation_id: str, owner_key: str) -> None:
        existing = self._owners.get(conversation_id)
        if existing is None:
            self._owners[conversation_id] = owner_key
            return
        if existing != owner_key:
            raise PermissionError("conversation owner mismatch")

    def owner(self, conversation_id: str) -> Optional[str]:
        return self._owners.get(conversation_id)

    def append(self, conversation_id: str, role: str, content: str) -> None:
        self._purge(conversation_id)
        bucket = self._store[conversation_id]
        bucket.append((role, content, datetime.utcnow()))
        while len(bucket) > self.max_messages:
            bucket.popleft()

    def history(self, conversation_id: str) -> List[ConversationEntry]:
        self._purge(conversation_id)
        return list(self._store.get(conversation_id, []))

    def _purge(self, conversation_id: str) -> None:
        bucket = self._store.get(conversation_id)
        if not bucket:
            return
        cutoff = datetime.utcnow() - self.ttl
        while bucket and bucket[0][2] < cutoff:
            bucket.popleft()
        if not bucket and conversation_id in self._owners:
            self._owners.pop(conversation_id, None)
