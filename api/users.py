"""
User model and store for Phase 4 RBAC.
Users are loaded from a JSON file (USERS_FILE env var) at startup.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    admin = "admin"
    senior_lawyer = "senior_lawyer"
    junior_lawyer = "junior_lawyer"
    reviewer = "reviewer"
    readonly = "readonly"


class User(BaseModel):
    user_id: str
    name: str
    email: str
    role: UserRole
    hashed_pwd: str
    is_active: bool = True


class UserStore:
    """Load users from a JSON file into memory.

    File path comes from USERS_FILE env var or explicit constructor arg.
    If the file does not exist or is empty, the store starts empty.
    """

    def __init__(self, path: str | None = None) -> None:
        self._by_email: dict[str, User] = {}
        self._by_id: dict[str, User] = {}
        if path:
            self._load(path)

    def _load(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            logger.warning("Users file not found: %s — starting with empty user store", path)
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for item in data:
                user = User.model_validate(item)
                self._by_email[user.email] = user
                self._by_id[user.user_id] = user
            logger.info("Loaded %d users from %s", len(self._by_id), path)
        except Exception:
            logger.exception("Failed to load users from %s", path)

    def get_by_email(self, email: str) -> Optional[User]:
        return self._by_email.get(email)

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self._by_id.get(user_id)

    def list_all(self) -> list[User]:
        return list(self._by_id.values())
