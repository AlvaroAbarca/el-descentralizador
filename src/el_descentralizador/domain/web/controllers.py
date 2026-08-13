from __future__ import annotations

from typing import Annotated

from litestar import Controller, Request, get, post
from litestar.enums import RequestEncodingType
from litestar.params import Body, FromPath
from litestar.response import Redirect, Template

from el_descentralizador.domain.accounts.guards import requires_admin
from el_descentralizador.domain.accounts.schemas import LoginRequest
from el_descentralizador.domain.accounts.services import UserService
from el_descentralizador.lib.di import Injected
from el_descentralizador.lib.exceptions import NotFoundError
from el_descentralizador.lib.settings import get_settings


class HealthController(Controller):
    path = "/health"
    tags = ["Health"]

    @get("/")
    async def health(self) -> dict[str, str]:
        return {"status": "ok"}


class WebController(Controller):
    path = "/"
    tags = ["Web"]

    @get("/")
    async def index(self, request: Request) -> Template:
        settings = get_settings()
        is_admin = request.user is not None
        return Template(
            template_name="index.html",
            context={
                "is_admin": is_admin,
                "repo_url": settings.repo_url,
            },
        )

    @get("/login")
    async def login_page(self, request: Request) -> Template:
        error = request.query_params.get("error")
        return Template(template_name="login.html", context={"error": bool(error)})

    @post("/login")
    async def login_form(
        self,
        request: Request,
        data: Annotated[LoginRequest, Body(media_type=RequestEncodingType.URL_ENCODED)],
        user_service: Injected[UserService],
    ) -> Redirect:
        user = await user_service.authenticate(data.username, data.password)
        if user is None:
            return Redirect(path="/login?error=1")
        request.set_session({"user_id": str(user.id), "username": user.username})
        return Redirect(path="/")

    @post("/logout")
    async def logout(self, request: Request) -> Redirect:
        request.clear_session()
        return Redirect(path="/")

    @get("/curator/{kind:str}", guards=[requires_admin])
    async def curator(self, kind: FromPath[str]) -> Template:
        if kind not in {"media", "municipalities"}:
            raise NotFoundError("Unknown curator kind")
        return Template(template_name="curator.html", context={"kind": kind})
