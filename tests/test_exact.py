"""Tests for exact duplicate detection."""

from mediadedup.detectors.exact import find_exact_duplicates


def test_finds_files_with_identical_contents(tmp_path):
    """Files with identical contents should be grouped."""

    file_a = tmp_path / "photo_a.jpg"
    file_b = tmp_path / "photo_b.jpg"
    file_c = tmp_path / "photo_c.jpg"

    file_a.write_bytes(b"identical image data")
    file_b.write_bytes(b"identical image data")
    file_c.write_bytes(b"different image data")

    result = find_exact_duplicates([file_a, file_b, file_c])

    assert result == [[file_a, file_b]]


def test_different_contents_are_not_grouped(tmp_path):
    """Files with different contents should not be duplicates."""

    file_a = tmp_path / "one.bin"
    file_b = tmp_path / "two.bin"

    file_a.write_bytes(b"first file")
    file_b.write_bytes(b"second file")

    assert find_exact_duplicates([file_a, file_b]) == []


def test_single_file_has_no_duplicates(tmp_path):
    """A single file cannot form a duplicate group."""

    file_a = tmp_path / "only.bin"
    file_a.write_bytes(b"single file")

    assert find_exact_duplicates([file_a]) == []


def test_empty_input_returns_empty_result():
    """An empty input should return no duplicate groups."""

    assert find_exact_duplicates([]) == []


def test_finds_multiple_duplicate_groups(tmp_path):
    """Separate sets of identical files should form separate groups."""

    files = [
        tmp_path / "a.bin",
        tmp_path / "b.bin",
        tmp_path / "c.bin",
        tmp_path / "d.bin",
    ]

    files[0].write_bytes(b"group one")
    files[1].write_bytes(b"group one")
    files[2].write_bytes(b"group two")
    files[3].write_bytes(b"group two")

    result = find_exact_duplicates(files)

    assert result == [
        [files[0], files[1]],
        [files[2], files[3]],
    ]