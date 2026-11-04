"""Perceptual image similarity detection."""

from pathlib import Path

import imagehash
from PIL import Image, ImageOps


def perceptual_hash(
    image_path: str | Path,
    hash_size: int = 8,
) -> imagehash.ImageHash:
    """Calculate a perceptual hash for an image.

    EXIF orientation is applied before hashing so that rotated
    camera images are compared in their correct orientation.
    """
    if hash_size <= 0:
        raise ValueError("hash_size must be greater than zero")

    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        return imagehash.phash(image, hash_size=hash_size)


def hamming_distance(
    hash_a: imagehash.ImageHash,
    hash_b: imagehash.ImageHash,
) -> int:
    """Return the number of differing bits between two hashes."""
    return hash_a - hash_b