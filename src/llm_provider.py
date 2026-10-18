"""Provider contract. Implementations never own memory, evidence or database writes."""
from typing import Protocol


class ChatProvider(Protocol):
    def identify(self, name: str, rows=None) -> dict: ...
    def chat(self, model: str, messages: list, schema=None, max_tokens=384) -> tuple: ...
