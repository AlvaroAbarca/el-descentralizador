from __future__ import annotations

from collections.abc import AsyncGenerator

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy.ext.asyncio import AsyncSession

from el_descentralizador.db.models.user import User


class UserService(SQLAlchemyAsyncRepositoryService[User]):
    class Repo(SQLAlchemyAsyncRepository[User]):
        model_type = User

    repository_type = Repo

    async def authenticate(self, username: str, password: str) -> User | None:
        user = await self.get_one_or_none(username=username)
        if user is None or not user.is_active:
            return None
        if not user.password.verify(password):
            return None
        return user


async def provide_user_service(db_session: AsyncSession) -> AsyncGenerator[UserService]:
    async with UserService.new(session=db_session) as service:
        yield service
