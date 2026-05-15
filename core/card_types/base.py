from abc import ABC, abstractmethod


class CardTypeValidationError(ValueError):
    pass


class CardTypeHandler(ABC):
    key = ""
    anki_notetype_name = ""

    @property
    def notetype_candidates(self) -> tuple[str, ...]:
        return (self.anki_notetype_name,)

    @abstractmethod
    def normalize(self, card: dict, default_deck: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def populate_note(self, note, card: dict, image_html: str) -> None:
        raise NotImplementedError
