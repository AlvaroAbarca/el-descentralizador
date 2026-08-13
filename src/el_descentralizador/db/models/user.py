from advanced_alchemy.base import UUIDv7AuditBase
from advanced_alchemy.types import PasswordHash
from advanced_alchemy.types.password_hash.argon2 import Argon2Hasher
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class User(UUIDv7AuditBase):
    """Single admin account used for session login."""

    __tablename__ = "user_account"

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password: Mapped[str] = mapped_column(PasswordHash(backend=Argon2Hasher()))
    is_active: Mapped[bool] = mapped_column(default=True)
