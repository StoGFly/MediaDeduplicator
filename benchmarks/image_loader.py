
"""Shared image loading and normalisation for benchmarks."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class LoadedImage:
    """Consistently decoded and orientation-corrected image."""

    path: Path
    rgb: np.ndarray
    gray: np.ndarray
    width: int
    height: int


class ImageLoadError(Exception):
    """Raised when an image cannot be loaded."""


def load_image(path: str | Path) -> LoadedImage:
    """Load an image with EXIF orientation applied.

    All benchmark detectors receive the same normalised image:
    - RGB: uint8, three channels
    - Gray: uint8, single channel
    - EXIF orientation applied before conversion
    """

    path = Path(path)

    try:
        with Image.open(path) as source:
            oriented = ImageOps.exif_transpose(source)
            rgb_image = oriented.convert("RGB")

            rgb = np.asarray(
                rgb_image,
                dtype=np.uint8,
            ).copy()

            gray = np.asarray(
                rgb_image.convert("L"),
                dtype=np.uint8,
            ).copy()

            width, height = rgb_image.size

    except (OSError, ValueError) as exc:
        raise ImageLoadError(
            f"Could not load image '{path}': {exc}"
        ) from exc

    return LoadedImage(
        path=path,
        rgb=rgb,
        gray=gray,
        width=width,
        height=height,
    )
