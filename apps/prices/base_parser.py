from __future__ import annotations

from abc import ABC, abstractmethod


class BaseParser(ABC):

    @abstractmethod
    def parse_category(self, category_url: str) -> list:
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    def __enter__(self) -> BaseParser:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

