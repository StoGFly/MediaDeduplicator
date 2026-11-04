
"""Tests for perceptual image hashing."""

import imagehash
import pytest
from PIL import Image, ImageDraw

from mediadedup.detectors.image import (
    hamming_distance,
    perceptual_hash,
)


def create_test_image(path, size=(200, 200)):
    """Create a test image with recognisable shapes."""
    image = Image.new("RGB", size, "red")
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 50, 150, 150), fill="blue")
    draw.ellipse((75, 75, 125, 125), fill="yellow")
    image.save(path)


def create_checkerboard(path, size=(200, 200)):
    """Create a visually different checkerboard image."""
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)

    square_size = 25

    for y in range(0, size[1], square_size):
        for x in range(0, size[0], square_size):
            if (x // square_size + y // square_size) % 2 == 0:
                draw.rectangle(
                    (x, y, x + square_size - 1, y + square_size - 1),
                    fill="black",
                )

    image.save(path)


def test_perceptual_hash_returns_image_hash(tmp_path):
    image_path = tmp_path / "photo.png"
    create_test_image(image_path)

    result = perceptual_hash(image_path)

    assert isinstance(result, imagehash.ImageHash)
    assert result.hash.size == 64


def test_identical_images_have_zero_distance(tmp_path):
    image_a = tmp_path / "photo_a.png"
    image_b = tmp_path / "photo_b.png"

    create_test_image(image_a)
    create_test_image(image_b)

    hash_a = perceptual_hash(image_a)
    hash_b = perceptual_hash(image_b)

    assert hamming_distance(hash_a, hash_b) == 0


def test_different_images_have_nonzero_distance(tmp_path):
    image_a = tmp_path / "photo.png"
    image_b = tmp_path / "checkerboard.png"

    create_test_image(image_a)
    create_checkerboard(image_b)

    hash_a = perceptual_hash(image_a)
    hash_b = perceptual_hash(image_b)

    assert hamming_distance(hash_a, hash_b) > 0


def test_resized_and_recompressed_image_has_similar_hash(tmp_path):
    original_path = tmp_path / "original.png"
    altered_path = tmp_path / "resized.jpg"

    create_test_image(original_path)

    with Image.open(original_path) as original:
        resized = original.resize((100, 100), Image.Resampling.LANCZOS)
        resized.save(altered_path, quality=70)

    original_hash = perceptual_hash(original_path)
    altered_hash = perceptual_hash(altered_path)

    assert hamming_distance(original_hash, altered_hash) <= 12


def test_perceptual_hash_rejects_invalid_hash_size(tmp_path):
    image_path = tmp_path / "photo.png"
    create_test_image(image_path)

    with pytest.raises(ValueError):
        perceptual_hash(image_path, hash_size=0)


def test_hamming_distance_returns_exact_bit_difference():
    hash_a = imagehash.hex_to_hash("0000000000000000")
    hash_b = imagehash.hex_to_hash("0000000000000001")

    assert hamming_distance(hash_a, hash_b) == 1
