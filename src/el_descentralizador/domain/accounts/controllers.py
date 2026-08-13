from __future__ import annotations

from litestar import Controller, Request, Response, get, post

from el_descentralizador.domain.accounts.auth import UserSession
from el_descentralizador.domain.accounts.schemas import LoginRequest, LoginResponse
from el_descentralizador.domain.accounts.services import UserService
from el_descentralizador.lib.di import Injected
from el_descentralizador.lib.exceptions import PermissionError


class AuthController(Controller):
    path = "/auth"
    tags = ["Auth"]

    @post("/login", status_code=200)
    async def login(
        self,
        request: Request,
        data: LoginRequest,
        user_service: Injected[UserService],
    ) -> LoginResponse:
        user = await user_service.authenticate(data.username, data.password)
        if user is None:
            raise PermissionError("Invalid credentials")
        request.set_session({"user_id": str(user.id), "username": user.username})
        return LoginResponse(username=user.username)

    @post("/logout")
    async def logout(self, request: Request) -> Response[dict[str, bool]]:
        request.clear_session()
        return Response(content={"ok": True})

    @get("/me")
    async def me(self, request: Request[UserSession | None, None, None]) -> LoginResponse:
        if request.user is None:
            raise PermissionError("Authentication required")
        return LoginResponse(username=request.user.username)
