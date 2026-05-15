from abc import ABC, abstractmethod


class ModelProvider(ABC):
    key = ""
    display_name = ""
    default_model = ""
    requires_api_key = True
    api_key_placeholder = ""

    @abstractmethod
    def generate_cards(self, prompt_data: dict, config: dict) -> list:
        raise NotImplementedError
