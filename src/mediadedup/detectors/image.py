"""Perceptual image similarity detection."""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import imagehash
import numpy as np

from PIL import Image, ImageOps


@dataclass(frozen=True)
class ImageMetadata:
    """Metadata extracted from an image file."""

    path: Path
    file_size: int
    width: int
    height: int
    format: str | None
    mode: str
    exif_orientation: int | None
    camera_make: str | None
    camera_model: str | None
    date_taken: str | None

def extract_image_metadata(
    image_path: str | Path,
) -> ImageMetadata:
    """Extract basic image and EXIF metadata."""
    path = Path(image_path)
    file_size = path.stat().st_size

    with Image.open(path) as image:
        try:
            exif = image.getexif()

            orientation = exif.get(274)
            camera_make = exif.get(271)
            camera_model = exif.get(272)
            date_taken = exif.get(36867) or exif.get(306)

        except (OSError, ValueError, TypeError):
            orientation = None
            camera_make = None
            camera_model = None
            date_taken = None

        return ImageMetadata(
            path=path,
            file_size=file_size,
            width=image.width,
            height=image.height,
            format=image.format,
            mode=image.mode,
            exif_orientation=orientation,
            camera_make=str(camera_make).strip() if camera_make else None,
            camera_model=str(camera_model).strip() if camera_model else None,
            date_taken=str(date_taken).strip() if date_taken else None,
        )


@dataclass(frozen=True)
class ImageComparison:
    """Evidence produced by comparing two images."""

    path_a: Path
    path_b: Path
    hash_a: str
    hash_b: str
    distance: int
    hash_bits: int
    similarity_percent: float


@dataclass(frozen=True)
class SSIMComparison:
    """Evidence produced by structural image comparison."""

    path_a: Path
    path_b: Path
    similarity_score: float
    similarity_percent: float


def compare_images_ssim(
    file_a: str | Path,
    file_b: str | Path,
) -> SSIMComparison:
    """Compare two images using structural similarity (SSIM)."""
    from skimage.metrics import structural_similarity

    path_a = Path(file_a)
    path_b = Path(file_b)

    with Image.open(path_a) as image_a:
        image_a = ImageOps.exif_transpose(image_a)
        image_a = image_a.convert("L")

        with Image.open(path_b) as image_b:
            image_b = ImageOps.exif_transpose(image_b)
            image_b = image_b.convert("L")

            # Check whether the images have compatible proportions.
            ratio_a = image_a.width / image_a.height
            ratio_b = image_b.width / image_b.height

            if not math.isclose(
                ratio_a,
                ratio_b,
                rel_tol=0.02,
            ):
                raise ValueError(
                    "Images have incompatible aspect ratios"
                )

            # Use the smaller image dimensions as a common canvas.
            target_width = min(image_a.width, image_b.width)
            target_height = min(image_a.height, image_b.height)

            if min(target_width, target_height) < 7:
                raise ValueError(
                    "Images must be at least 7 pixels wide and high"
                )

            # Fit each image without changing its aspect ratio.
            image_a = ImageOps.pad(
                image_a,
                (target_width, target_height),
                method=Image.Resampling.LANCZOS,
            )
            image_b = ImageOps.pad(
                image_b,
                (target_width, target_height),
                method=Image.Resampling.LANCZOS,
            )

            score = structural_similarity(
                np.asarray(image_a),
                np.asarray(image_b),
                data_range=255,
            )

    return SSIMComparison(
        path_a=path_a,
        path_b=path_b,
        similarity_score=float(score),
        similarity_percent=float(score * 100),
    )


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


def difference_hash(
    image_path: str | Path,
    hash_size: int = 8,
) -> imagehash.ImageHash:
    """Calculate a difference hash (dHash) for an image.

    EXIF orientation is applied before hashing so that rotated
    camera images are compared in their correct orientation.
    """
    if hash_size <= 0:
        raise ValueError("hash_size must be greater than zero")

    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        return imagehash.dhash(image, hash_size=hash_size)


def hamming_distance(
    hash_a: imagehash.ImageHash,
    hash_b: imagehash.ImageHash,
) -> int:
    """Return the number of differing bits between two hashes."""
    return int(hash_a - hash_b)


def compare_images(
    file_a: str | Path,
    file_b: str | Path,
    hash_size: int = 8,
) -> ImageComparison:
    """Compare two images and return their similarity evidence."""
    path_a = Path(file_a)
    path_b = Path(file_b)

    hash_a = perceptual_hash(path_a, hash_size)
    hash_b = perceptual_hash(path_b, hash_size)

    distance = hamming_distance(hash_a, hash_b)
    hash_bits = hash_a.hash.size

    similarity_percent = (
        (hash_bits - distance) / hash_bits
    ) * 100

    return ImageComparison(
        path_a=path_a,
        path_b=path_b,
        hash_a=str(hash_a),
        hash_b=str(hash_b),
        distance=distance,
        hash_bits=hash_bits,
        similarity_percent=similarity_percent,
    )


def compare_images_dhash(
    file_a: str | Path,
    file_b: str | Path,
    hash_size: int = 8,
) -> ImageComparison:
    """Compare two images using difference hashing."""
    path_a = Path(file_a)
    path_b = Path(file_b)

    hash_a = difference_hash(path_a, hash_size)
    hash_b = difference_hash(path_b, hash_size)

    distance = hamming_distance(hash_a, hash_b)
    hash_bits = hash_a.hash.size

    similarity_percent = (
        (hash_bits - distance) / hash_bits
    ) * 100

    return ImageComparison(
        path_a=path_a,
        path_b=path_b,
        hash_a=str(hash_a),
        hash_b=str(hash_b),
        distance=distance,
        hash_bits=hash_bits,
        similarity_percent=similarity_percent,
    )


def meets_similarity_threshold(
    comparison: ImageComparison,
    minimum_similarity: float = 85.0,
) -> bool:
    """Check whether an image comparison meets a minimum similarity.

    Args:
        comparison: Image comparison evidence.
        minimum_similarity: Required similarity percentage (0–100).

    Returns:
        True if the comparison meets or exceeds the threshold.

    Raises:
        ValueError: If the threshold is outside 0–100 or not finite.
    """
    if (
        not math.isfinite(minimum_similarity)
        or not 0.0 <= minimum_similarity <= 100.0
    ):
        raise ValueError(
            "minimum_similarity must be between 0 and 100"
        )

    return comparison.similarity_percent >= minimum_similarity


def find_similar_image_pairs(
    file_paths: Iterable[str | Path],
    minimum_similarity: float = 85.0,
    hash_size: int = 8,
) -> list[ImageComparison]:
    """Find image pairs meeting the minimum similarity threshold.

    Each image is hashed once. Every unique pair is compared once.

    Args:
        file_paths: Image paths to compare.
        minimum_similarity: Minimum accepted similarity percentage.
        hash_size: Perceptual hash size.

    Returns:
        Matching image pairs, sorted by descending similarity.

    Raises:
        ValueError: If the threshold or hash size is invalid.
        OSError: If an image cannot be opened or read.
    """
    if (
        not math.isfinite(minimum_similarity)
        or not 0.0 <= minimum_similarity <= 100.0
    ):
        raise ValueError(
            "minimum_similarity must be between 0 and 100"
        )

    if hash_size <= 0:
        raise ValueError("hash_size must be greater than zero")

    paths = list(dict.fromkeys(Path(path) for path in file_paths))

    # Calculate each image hash only once.
    hashes = {
        path: perceptual_hash(path, hash_size)
        for path in paths
    }

    matching_pairs = []

    for path_a, path_b in combinations(paths, 2):
        hash_a = hashes[path_a]
        hash_b = hashes[path_b]

        distance = hamming_distance(hash_a, hash_b)
        hash_bits = hash_a.hash.size

        similarity_percent = (
            (hash_bits - distance) / hash_bits
        ) * 100

        comparison = ImageComparison(
            path_a=path_a,
            path_b=path_b,
            hash_a=str(hash_a),
            hash_b=str(hash_b),
            distance=distance,
            hash_bits=hash_bits,
            similarity_percent=similarity_percent,
        )

        if meets_similarity_threshold(
            comparison,
            minimum_similarity,
        ):
            matching_pairs.append(comparison)

    matching_pairs.sort(
        key=lambda comparison: comparison.similarity_percent,
        reverse=True,
    )

    return matching_pairs