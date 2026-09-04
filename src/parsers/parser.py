from abc import ABC, abstractmethod

from src.utils.dataclasses import RawPublication


class Parser(ABC):
    """Base contract for all external data parsers."""

    @abstractmethod
    async def parse(self) -> list[RawPublication]:
        """
        Extract publications from an external source.

        Returns:
            List of raw publications extracted from the source.
        """
        raise NotImplementedError