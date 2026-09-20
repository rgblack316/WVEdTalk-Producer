"""User accounts for multi-user auth. The stored document also holds `password_hash`,
which is deliberately NOT part of the public `User` model, so it never reaches the client.
Mirrored in frontend/src/lib/types.ts."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

ROLES = {"admin", "editor"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(BaseModel):
    """Client-visible shape — never includes the password hash."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    role: str = "editor"  # admin | editor
    created_at: datetime = Field(default_factory=_now)


class UserCreate(BaseModel):
    email: EmailStr
    role: str = "editor"


class RoleUpdate(BaseModel):
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class AuthState(BaseModel):
    authenticated: bool
    user: Optional[User] = None


class CreatedUser(BaseModel):
    """Returned once when an admin creates a user or resets a password — carries the
    one-time temporary password the admin must relay to the new user."""

    user: User
    temp_password: str
