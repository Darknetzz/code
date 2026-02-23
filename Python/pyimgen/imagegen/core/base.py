"""Abstract base for all image generators (procedural now, API later)."""

from abc import ABC, abstractmethod
from typing import Any

from PIL import Image


class Generator(ABC):
    """Base class for image generators. Subclass to add procedural or API-backed backends."""

    @abstractmethod
    def generate(
        self,
        prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        **kwargs: Any,
    ) -> Image.Image:
        """
        Generate an image.

        Args:
            prompt: Text description (used by API generators; procedural may use as preset hint).
            width: Output width in pixels.
            height: Output height in pixels.
            **kwargs: Generator-specific options.

        Returns:
            PIL Image (RGB or RGBA).
        """
        pass
