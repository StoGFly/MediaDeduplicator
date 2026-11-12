"""File hashing utilities."""

import hashlib
from pathlib import Path


def sha256_file(
    file_path: str | Path,
    chunk_size: int = 1024 * 1024,
    *,
    on_chunk=None,
) -> str:
    """Calculate the SHA-256 hash of a file without loading it all into memory.

    Args:
        file_path: Path to the file to hash.
        chunk_size: Number of bytes to read per iteration.
        on_chunk: Optional callback receiving the number of bytes just hashed.

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
            if on_chunk is not None:
                on_chunk(len(chunk))

    return digest.hexdigest()


def file_fingerprint(path: Path) -> tuple[int, int, int, int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
