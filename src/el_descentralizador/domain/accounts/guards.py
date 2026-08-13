from __future__ import annotations

from litestar.connection import ASGIConnection
from litestar.exceptions import HTTPException, NotAuthorizedException
from litestar.handlers import BaseRouteHandler


async def requires_admin(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    if connection.user is not None:
        return
    accept = connection.headers.get("accept", "")
    if "text/html" in accept:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    raise NotAuthorizedException("Authentication required")
