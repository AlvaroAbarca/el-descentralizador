import msgspec

from el_descentralizador.lib.schema import CamelizedBaseStruct


class LoginRequest(msgspec.Struct, kw_only=True):
    username: str
    password: str


class LoginResponse(CamelizedBaseStruct):
    username: str
