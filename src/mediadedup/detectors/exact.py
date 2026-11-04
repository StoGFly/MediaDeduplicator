"""Exact duplicate file detection."""

from collections import defaultdict
from pathlib import Path
from typing import Iterable

from mediadedup.core.hashing import sha256_file


def find_exact_duplicates(
    file_paths: Iterable[str | Path],
) -> list[list[Path]]:
    """Find groups of files with identical SHA-256 hashes.

    Args:
        file_paths: Files to compare.

    Returns:
        Groups containing two or more files with identical contents.
        Files within each group retain their input order.

    Raises:
        OSError: If a file cannot be opened or read.
    """
    files_by_hash: dict[str, list[Path]] = defaultdict(list)

    for file_path in file_paths:
        path = Path(file_path)
        file_hash = sha256_file(path)
        files_by_hash[file_hash].append(path)

    return [
        paths
        for paths in files_by_hash.values()
        if len(paths) > 1
    ]