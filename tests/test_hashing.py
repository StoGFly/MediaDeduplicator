"""Tests for file hashing utilities."""

import hashlib

import pytest

from mediadedup.core.hashing import sha256_file


def test_sha256_file(tmp_path):
    """Hash a file and compare it with hashlib's expected result."""

    test_file = tmp_path / "sample.bin"
    test_file.write_bytes(b"MediaDeduplicator test data")

    expected = hashlib.sha256(b"MediaDeduplicator test data").hexdigest()

    assert sha256_file(test_file) == expected


def test_sha256_file_accepts_string_path(tmp_path):
    """The hashing function should accept a string path."""

    test_file = tmp_path / "sample.txt"
    test_file.write_text("Hello MediaDeduplicator", encoding="utf-8")

    assert sha256_file(str(test_file)) == hashlib.sha256(
        b"Hello MediaDeduplicator"
    ).hexdigest()


def test_sha256_file_with_small_chunks(tmp_path):
    """Hashing should work when files are read in small chunks."""

    test_file = tmp_path / "chunked.bin"
    contents = b"0123456789" * 100
    test_file.write_bytes(contents)

    assert sha256_file(test_file, chunk_size=7) == hashlib.sha256(
        contents
    ).hexdigest()


def test_sha256_file_rejects_zero_chunk_size(tmp_path):
    """A zero chunk size should raise ValueError."""

    test_file = tmp_path / "sample.bin"
    test_file.write_bytes(b"test")

    with pytest.raises(ValueError):
        sha256_file(test_file, chunk_size=0)


def test_sha256_file_rejects_negative_chunk_size(tmp_path):
    """A negative chunk size should raise ValueError."""

    test_file = tmp_path / "sample.bin"
    test_file.write_bytes(b"test")

    with pytest.raises(ValueError):
        sha256_file(test_file, chunk_size=-1)