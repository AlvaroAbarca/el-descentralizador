import msgspec


class CamelizedBaseStruct(msgspec.Struct, rename="camel", kw_only=True):
    """snake_case in Python, camelCase on the wire."""

    def to_dict(self) -> dict:
        return msgspec.to_builtins(self)
