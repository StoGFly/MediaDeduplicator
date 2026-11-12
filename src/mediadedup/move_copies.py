"""Relocate verified extra copies while retaining a matching original."""

import errno
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from mediadedup.core.hashing import file_fingerprint, sha256_file


def plan_move_targets(scan_folder, destination, copies):
    """Choose distinct destinations without overwriting existing files."""
    if scan_folder.samefile(destination):
        raise ValueError("Choose a destination other than the scanned folder.")

    requested = {
        source: destination / source.relative_to(scan_folder)
        for source in copies
    }
    reserved = set(requested.values())
    jobs = []
    for source, target in requested.items():
        keeper, _ = copies[source]
        occupied = target.exists() or target.is_symlink()
        if occupied and source.exists() and target.exists() and source.samefile(target):
            raise ValueError(f"The destination points to the source file: {source}")

        if occupied:
            number = 1
            while True:
                candidate = target.with_name(f"{target.stem} ({number}){target.suffix}")
                if candidate not in reserved and not candidate.exists() and not candidate.is_symlink():
                    target = candidate
                    reserved.add(target)
                    break
                number += 1
        jobs.append((keeper, source, target))
    return jobs


def move_copy(keeper, source, destination, *, on_moving=None):
    """Move a byte-identical copy to a new path on Windows."""
    if keeper == source or keeper.is_symlink() or source.is_symlink():
        raise ValueError("Choose a separate regular file to keep.")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")
    keeper_state = file_fingerprint(keeper)
    source_state = file_fingerprint(source)
    digest = sha256_file(keeper)
    if sha256_file(source) != digest:
        raise ValueError("The files no longer match.")
    if file_fingerprint(keeper) != keeper_state or file_fingerprint(source) != source_state:
        raise ValueError("A file changed during verification.")
    if on_moving is not None:
        on_moving(digest)

    def unchanged():
        return file_fingerprint(source) == source_state and file_fingerprint(keeper) == keeper_state

    relocate_verified(source, destination, digest, unchanged)


def restore_copy(source, destination, digest):
    """Restore a recycled file only if it matches the recorded digest."""
    if source == destination or destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Restore path already exists: {destination}")
    if source.is_symlink():
        raise ValueError("The recycle path points to a link.")
    signature = file_fingerprint(source)
    if sha256_file(source) != digest:
        raise ValueError("The recycled file no longer matches its recorded hash.")

    def unchanged():
        return file_fingerprint(source) == signature

    relocate_verified(source, destination, digest, unchanged)


def relocate_verified(source, destination, digest, unchanged):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")
    if not unchanged():
        raise ValueError("A file changed during verification.")
    try:
        # Windows rename refuses an existing destination.
        source.rename(destination)
        return
    except OSError as error:
        if error.errno != errno.EXDEV and getattr(error, "winerror", None) != 17:
            raise

    with TemporaryDirectory(prefix=".mediadedup-", dir=destination.parent) as directory:
        staged = Path(directory) / "copy"
        shutil.copy2(source, staged)
        if sha256_file(staged) != digest or not unchanged():
            raise ValueError("A file changed during the move.")
        staged.rename(destination)
        try:
            if not unchanged():
                raise OSError("A file changed after the verified copy was written.")
            source.unlink()
        except OSError as error:
            raise OSError(f"Verified copy saved to {destination}, but the source remains: {error}") from error
