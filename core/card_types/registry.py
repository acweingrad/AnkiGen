from .builtin import BUILTIN_CARD_TYPES

_CARD_TYPE_HANDLERS = {}


def register_card_type(handler) -> None:
    _CARD_TYPE_HANDLERS[handler.key] = handler


def get_card_type_handler(card_type: str):
    return _CARD_TYPE_HANDLERS.get(card_type)


def get_default_card_type_handler():
    return _CARD_TYPE_HANDLERS["basic"]


def list_card_type_handlers() -> list:
    return list(_CARD_TYPE_HANDLERS.values())


for _handler in BUILTIN_CARD_TYPES:
    register_card_type(_handler)
