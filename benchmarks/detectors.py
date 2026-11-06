"""Benchmark adapters for production image similarity detectors."""

from pathlib import Path

from mediadedup.detectors.image import (
    compare_images,
    compare_images_dhash,
    compare_images_ssim,
)


def compare_phash(path_a: str | Path, path_b: str | Path) -> dict:
    """Run the production perceptual hash comparison."""

    result = compare_images(path_a, path_b)

    return {
        "status": "ok",
        "distance": result.distance,
        "hash_bits": result.hash_bits,
        "similarity_percent": result.similarity_percent,
        "hash_a": result.hash_a,
        "hash_b": result.hash_b,
    }


def compare_dhash(path_a: str | Path, path_b: str | Path) -> dict:
    """Run the production difference hash comparison."""

    result = compare_images_dhash(path_a, path_b)

    return {
        "status": "ok",
        "distance": result.distance,
        "hash_bits": result.hash_bits,
        "similarity_percent": result.similarity_percent,
        "hash_a": result.hash_a,
        "hash_b": result.hash_b,
    }


def compare_ssim(path_a: str | Path, path_b: str | Path) -> dict:
    """Run the production SSIM comparison."""

    try:
        result = compare_images_ssim(path_a, path_b)

    except ValueError as exc:
        if "aspect ratios" in str(exc).lower():
            return {
                "status": "not_comparable",
                "error": str(exc),
            }

        raise

    return {
        "status": "ok",
        "similarity_score": result.similarity_score,
        "similarity_percent": result.similarity_percent,
        "rotation_degrees": result.rotation_degrees,
    }