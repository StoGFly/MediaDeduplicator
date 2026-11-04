"""Tests for perceptual image hashing."""

from pathlib import Path

import imagehash
import pytest
from PIL import Image, ImageDraw

from mediadedup.detectors.image import (
    ImageComparison,
    ImageMetadata,
    compare_images,
    compare_images_dhash,
    difference_hash,
    extract_image_metadata,
    find_similar_image_pairs,
    hamming_distance,
    meets_similarity_threshold,
    perceptual_hash,
)


def make_comparison(similarity_percent):
    """Create comparison evidence for threshold tests."""
    return ImageComparison(
        path_a=Path("image_a.png"),
        path_b=Path("image_b.png"),
        hash_a="0000000000000000",
        hash_b="0000000000000001",
        distance=6,
        hash_bits=64,
        similarity_percent=similarity_percent,
    )


def test_similarity_threshold_accepts_exact_boundary():
    comparison = make_comparison(90.625)

    assert meets_similarity_threshold(comparison, 90.625)


def test_similarity_threshold_accepts_above_threshold():
    comparison = make_comparison(90.625)

    assert meets_similarity_threshold(comparison, 90.0)


def test_similarity_threshold_rejects_below_threshold():
    comparison = make_comparison(90.625)

    assert not meets_similarity_threshold(comparison, 91.0)


def test_similarity_threshold_uses_default_value():
    comparison = make_comparison(85.0)

    assert meets_similarity_threshold(comparison)


@pytest.mark.parametrize(
    "threshold",
    [-1.0, 100.1, float("nan"), float("inf"), float("-inf")],
)
def test_similarity_threshold_rejects_invalid_values(threshold):
    comparison = make_comparison(90.0)

    with pytest.raises(ValueError):
        meets_similarity_threshold(comparison, threshold)


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


def test_compare_images_returns_comparison_evidence(tmp_path):
    image_a = tmp_path / "photo_a.png"
    image_b = tmp_path / "photo_b.png"

    create_test_image(image_a)
    create_test_image(image_b)

    result = compare_images(image_a, image_b)

    assert isinstance(result, ImageComparison)
    assert result.path_a == image_a
    assert result.path_b == image_b
    assert result.hash_a
    assert result.hash_b
    assert result.distance == 0
    assert result.hash_bits == 64
    assert result.similarity_percent == 100.0


def test_compare_images_calculates_similarity_percentage(tmp_path):
    image_a = tmp_path / "original.png"
    image_b = tmp_path / "resized.jpg"

    create_test_image(image_a)

    with Image.open(image_a) as original:
        resized = original.resize(
            (100, 100),
            Image.Resampling.LANCZOS,
        )
        resized.save(image_b, quality=70)

    result = compare_images(image_a, image_b)

    expected = (
        (result.hash_bits - result.distance)
        / result.hash_bits
    ) * 100

    assert result.similarity_percent == expected
    assert 0 <= result.similarity_percent <= 100

def test_find_similar_image_pairs_finds_identical_images(tmp_path):
    image_a = tmp_path / "photo_a.png"
    image_b = tmp_path / "photo_b.png"

    create_test_image(image_a)
    create_test_image(image_b)

    results = find_similar_image_pairs(
        [image_a, image_b],
        minimum_similarity=85.0,
    )

    assert len(results) == 1
    assert results[0].path_a == image_a
    assert results[0].path_b == image_b
    assert results[0].similarity_percent == 100.0


def test_find_similar_image_pairs_filters_below_threshold(tmp_path):
    image_a = tmp_path / "photo.png"
    image_b = tmp_path / "checkerboard.png"

    create_test_image(image_a)
    create_checkerboard(image_b)

    results = find_similar_image_pairs(
        [image_a, image_b],
        minimum_similarity=100.0,
    )

    assert results == []


def test_find_similar_image_pairs_returns_no_pairs_for_one_image(tmp_path):
    image_a = tmp_path / "photo.png"
    create_test_image(image_a)

    results = find_similar_image_pairs([image_a])

    assert results == []


def test_find_similar_image_pairs_returns_no_pairs_for_empty_input():
    assert find_similar_image_pairs([]) == []


def test_find_similar_image_pairs_removes_repeated_paths(tmp_path):
    image_a = tmp_path / "photo.png"
    create_test_image(image_a)

    results = find_similar_image_pairs(
        [image_a, image_a, image_a]
    )

    assert results == []


def test_find_similar_image_pairs_rejects_invalid_threshold():
    with pytest.raises(ValueError):
        find_similar_image_pairs([], minimum_similarity=101.0)


def test_find_similar_image_pairs_rejects_invalid_hash_size():
    with pytest.raises(ValueError):
        find_similar_image_pairs([], hash_size=0)


def test_find_similar_image_pairs_hashes_each_image_once(
    tmp_path,
    monkeypatch,
):
    import mediadedup.detectors.image as image_detector

    image_paths = [
        tmp_path / "photo_a.png",
        tmp_path / "photo_b.png",
        tmp_path / "photo_c.png",
    ]

    for image_path in image_paths:
        create_test_image(image_path)

    original_function = image_detector.perceptual_hash
    hash_calls = []

    def counting_hash(image_path, hash_size=8):
        hash_calls.append(Path(image_path))
        return original_function(image_path, hash_size)

    monkeypatch.setattr(
        image_detector,
        "perceptual_hash",
        counting_hash,
    )

    image_detector.find_similar_image_pairs(
        image_paths,
        minimum_similarity=85.0,
    )

    assert len(hash_calls) == 3
    assert set(hash_calls) == set(image_paths)

def test_extract_image_metadata(tmp_path):
    image_path = tmp_path / "metadata.png"
    create_test_image(image_path)

    metadata = extract_image_metadata(image_path)

    assert isinstance(metadata, ImageMetadata)
    assert metadata.path == image_path
    assert metadata.file_size == image_path.stat().st_size
    assert metadata.width == 200
    assert metadata.height == 200
    assert metadata.format == "PNG"
    assert metadata.mode == "RGB"
    assert metadata.exif_orientation is None
    assert metadata.camera_make is None
    assert metadata.camera_model is None
    assert metadata.date_taken is None


def test_extract_image_metadata_with_exif(tmp_path):
    image_path = tmp_path / "camera.jpg"

    image = Image.new("RGB", (640, 480), "blue")
    exif = image.getexif()
    exif[274] = 6
    exif[271] = "Canon"
    exif[272] = "EOS Test"
    exif[36867] = "2026:11:04 12:00:00"
    image.save(image_path, exif=exif)

    metadata = extract_image_metadata(image_path)

    assert metadata.exif_orientation == 6
    assert metadata.camera_make == "Canon"
    assert metadata.camera_model == "EOS Test"
    assert metadata.date_taken == "2026:11:04 12:00:00"


def test_extract_image_metadata_handles_malformed_exif(
    tmp_path,
    monkeypatch,
):
    image_path = tmp_path / "malformed.png"
    create_test_image(image_path)

    def broken_exif(self):
        raise ValueError("Malformed EXIF data")

    monkeypatch.setattr(Image.Image, "getexif", broken_exif)

    metadata = extract_image_metadata(image_path)

    assert metadata.width == 200
    assert metadata.height == 200
    assert metadata.exif_orientation is None
    assert metadata.camera_make is None
    assert metadata.camera_model is None
    assert metadata.date_taken is None


def test_extract_image_metadata_missing_file(tmp_path):
    image_path = tmp_path / "missing.png"

    with pytest.raises(FileNotFoundError):
        extract_image_metadata(image_path)


def test_image_metadata_is_immutable(tmp_path):
    image_path = tmp_path / "immutable.png"
    create_test_image(image_path)

    metadata = extract_image_metadata(image_path)

    with pytest.raises(AttributeError):
        metadata.width = 999

def test_difference_hash_returns_image_hash(tmp_path):
    image_path = tmp_path / "image.png"
    create_test_image(image_path)

    result = difference_hash(image_path)

    assert isinstance(result, imagehash.ImageHash)
    assert result.hash.size == 64


def test_difference_hash_identical_images(tmp_path):
    image_a = tmp_path / "image_a.png"
    image_b = tmp_path / "image_b.png"

    create_test_image(image_a)
    create_test_image(image_b)

    hash_a = difference_hash(image_a)
    hash_b = difference_hash(image_b)

    assert hamming_distance(hash_a, hash_b) == 0


def test_difference_hash_different_images(tmp_path):
    image_a = tmp_path / "solid.png"
    image_b = tmp_path / "gradient.png"

    Image.new("RGB", (200, 200), "black").save(image_a)

    gradient = Image.new("L", (200, 200))
    for x in range(200):
        for y in range(200):
            gradient.putpixel((x, y), x)
    gradient.convert("RGB").save(image_b)

    hash_a = difference_hash(image_a)
    hash_b = difference_hash(image_b)

    assert hamming_distance(hash_a, hash_b) > 0


def test_difference_hash_invalid_hash_size(tmp_path):
    image_path = tmp_path / "image.png"
    create_test_image(image_path)

    with pytest.raises(ValueError):
        difference_hash(image_path, hash_size=0)

def test_compare_images_dhash_identical(tmp_path):
    image_a = tmp_path / "image_a.png"
    image_b = tmp_path / "image_b.png"

    create_test_image(image_a)
    create_test_image(image_b)

    comparison = compare_images_dhash(image_a, image_b)

    assert isinstance(comparison, ImageComparison)
    assert comparison.distance == 0
    assert comparison.hash_bits == 64
    assert comparison.similarity_percent == 100.0


def test_compare_images_dhash_different(tmp_path):
    image_a = tmp_path / "solid.png"
    image_b = tmp_path / "gradient.png"

    Image.new("RGB", (200, 200), "black").save(image_a)

    gradient = Image.new("L", (200, 200))
    for x in range(200):
        for y in range(200):
            gradient.putpixel((x, y), x)
    gradient.convert("RGB").save(image_b)

    comparison = compare_images_dhash(image_a, image_b)

    assert comparison.distance > 0
    assert comparison.similarity_percent < 100.0


def test_compare_images_dhash_evidence(tmp_path):
    image_a = tmp_path / "image_a.png"
    image_b = tmp_path / "image_b.png"

    create_test_image(image_a)
    create_test_image(image_b)

    comparison = compare_images_dhash(image_a, image_b)

    assert comparison.path_a == image_a
    assert comparison.path_b == image_b
    assert len(comparison.hash_a) == 16
    assert len(comparison.hash_b) == 16
    assert comparison.hash_bits == 64