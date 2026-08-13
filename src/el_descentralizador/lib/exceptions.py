from __future__ import annotations

from litestar import Request, Response
from litestar.exceptions import HTTPException


class ApplicationError(HTTPException):
    """Base class for application-level HTTP errors."""


class ApplicationClientError(ApplicationError):
    status_code = 400


class ValidationError(ApplicationClientError):
    status_code = 400


class NotFoundError(ApplicationClientError):
    status_code = 404


class ConflictError(ApplicationClientError):
    status_code = 409


class PermissionError(ApplicationClientError):
    status_code = 403


class DependencyError(ApplicationError):
    status_code = 502


def application_exception_handler(_request: Request, exc: ApplicationError) -> Response:
    return Response(
        content={"detail": exc.detail, "status_code": exc.status_code},
        status_code=exc.status_code,
    )
