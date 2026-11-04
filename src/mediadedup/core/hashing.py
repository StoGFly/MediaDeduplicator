"""File hashing utilities."""

import hashlib
from pathlib import Path


def sha256_file(
    file_path: str | Path,
    chunk_size: int = 1024 * 1024,
) -> str:
    """Calculate the SHA-256 hash of a file without loading it all into memory.

    Args:
        file_path: Path to the file to hash.
        chunk_size: Number of bytes to read per iteration.

    Returns:
        The file's SHA-256 digest as a lowercase hexadecimal string.

    Raises:
        ValueError: If chunk_size is not positive.
        OSError: If the file cannot be opened or read.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    digest = hashlib.sha256()

    with Path(file_path).open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)

    return digest.hexdigest()