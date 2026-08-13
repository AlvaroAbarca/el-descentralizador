from typing import Annotated, TypeVar

from litestar.params import Dependency

T = TypeVar("T")
Injected = Annotated[T, Dependency(skip_validation=True)]
