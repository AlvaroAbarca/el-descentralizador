from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from litestar.connection import ASGIConnection
from litestar.middleware.authentication import AuthenticationResult
from litestar.middleware.session.server_side import ServerSideSessionBackend, ServerSideSessionConfig
from litestar.security.session_auth import SessionAuth
from litestar.security.session_auth.middleware import SessionAuthMiddleware
from litestar.types import Empty


@dataclass(frozen=True)
class UserSession:
    id: UUID
    username: str


class OptionalSessionAuthMiddleware(SessionAuthMiddleware):
    """Allow anonymous access; populate ``connection.user`` when a session exists."""

    async def authenticate_request(self, connection: ASGIConnection[Any, Any, Any, Any]) -> AuthenticationResult:
        session = connection.scope.get("session")
        if not session or session is Empty:
            return AuthenticationResult(user=None, auth=None)
        user = await self.retrieve_user_handler(session, connection)
        if not user:
            return AuthenticationResult(user=None, auth=session)
        return AuthenticationResult(user=user, auth=session)


async def retrieve_user_handler(
    session: dict[str, Any],
    _connection: ASGIConnection,
) -> UserSession | None:
    raw_id = session.get("user_id")
    username = session.get("username")
    if raw_id is None or not username:
        return None
    try:
        return UserSession(id=UUID(str(raw_id)), username=str(username))
    except ValueError:
        return None


session_auth = SessionAuth[UserSession, ServerSideSessionBackend](
    retrieve_user_handler=retrieve_user_handler,
    session_backend_config=ServerSideSessionConfig(
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    ),
    authentication_middleware_class=OptionalSessionAuthMiddleware,
    exclude=["/schema", "/health"],
)
