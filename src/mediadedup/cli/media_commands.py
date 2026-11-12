"""Desktop media operations available without opening a window."""

from contextlib import contextmanager
from enum import Enum
from pathlib import Path
import sqlite3
from time import monotonic
from typing import Annotated

import typer


Folder = Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)]


class MediaScope(str, Enum):
    both = "both"
    photos = "photos"
    videos = "videos"


@contextmanager
def operation(history):
    from PySide6.QtCore import QLockFile

    history.path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(history.path) + ".operation.lock")
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise ValueError("Could not acquire the operation lock. A scan or move may already be running.")
    try:
        yield
    finally:
        lock.unlock()


def run_scan(folder, *, similarity, scope, threshold, hash_size, workers):
    from mediadedup.scan_history import ScanHistory
    from mediadedup.scan_job import Scan
    from mediadedup.scan_status import format_bytes

    history = ScanHistory()
    scan = Scan(folder, similarity, threshold, hash_size, history, None,
                scope=scope, hash_workers=workers)
    results = []
    errors = []
    stopped = []
    previous_phase = ""
    last_update = 0.0

    def progress(status):
        nonlocal previous_phase, last_update
        phase, done, total, _, _, _, bytes_checked = status
        now = monotonic()
        if phase == previous_phase and now - last_update < 3:
            return
        previous_phase, last_update = phase, now
        message = f"{phase} · {done:,}/{total:,}" if total else phase
        if bytes_checked is not None and bytes_checked[1]:
            message += f" · {format_bytes(bytes_checked[0])} / {format_bytes(bytes_checked[1])}"
        typer.echo(message, err=True)

    scan.completed.connect(lambda groups, count, scan_id: results.append((groups, count, scan_id)))
    scan.failed.connect(errors.append)
    scan.stopped.connect(stopped.append)
    scan.progress.connect(progress)
    try:
        with operation(history):
            scan.run()
    except (OSError, ValueError, sqlite3.Error) as error:
        errors.append(str(error))
    if stopped:
        typer.echo(f"Scan {stopped[0]} stopped. Resume it from desktop History.", err=True)
        raise typer.Exit(code=130)
    if not results:
        typer.echo(errors[0] if errors else "The scan produced no result.", err=True)
        raise typer.Exit(code=1)
    groups, count, scan_id = results[0]
    label = "similarity candidates" if similarity else "exact duplicate groups"
    typer.echo(f"Scan {scan_id} · {count:,} files · {len(groups):,} {label}")
    for title, files in groups:
        typer.echo(title)
        for path, size in files:
            typer.echo(f"  {path}  ({format_bytes(size)})")


def exact(
    folder: Folder,
    media: Annotated[MediaScope, typer.Option(help="Include photos, videos, or both.")] = MediaScope.both,
    workers: Annotated[int, typer.Option(min=1, max=8, help="Concurrent file reads.")] = 4,
):
    """Scan supported photos and videos for SHA-256 duplicates."""
    run_scan(folder, similarity=False, scope=media.value, threshold=85, hash_size=8, workers=workers)


def similar(
    folder: Folder,
    threshold: Annotated[float, typer.Option(min=0, max=100)] = 85.0,
    hash_size: Annotated[int, typer.Option(min=8, max=16)] = 8,
):
    """Find experimental pHash photo similarity candidates."""
    run_scan(folder, similarity=True, scope="photos", threshold=threshold, hash_size=hash_size, workers=4)


def overlap(folder_a: Folder, folder_b: Folder, media: MediaScope = MediaScope.both):
    """Compare exact matches across two separate folder trees."""
    from mediadedup.folder_overlap import CompareFolders
    from mediadedup.scan_history import ScanHistory
    from mediadedup.scan_status import format_bytes

    history = ScanHistory()
    try:
        with operation(history):
            results = CompareFolders((folder_a, folder_b), media.value, history, None).compare()
    except (OSError, ValueError, sqlite3.Error) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    for entry in results:
        unmatched = entry["unmatched"]
        typer.echo(f"{entry['folder']} · {entry['matched']:,}/{entry['files']:,} matched · {len(unmatched):,} only here")
        for path, size in unmatched:
            typer.echo(f"  {path}  ({format_bytes(size)})")


def history(limit: Annotated[int, typer.Option(min=1)] = 20):
    """List recent scans from the local SQLite history."""
    from mediadedup.scan_history import ScanHistory

    try:
        rows = ScanHistory().list_scans()
    except (OSError, sqlite3.Error) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    for row in rows[:limit]:
        mode = "similar" if row["similarity"] else f"exact/{row['scope']}"
        counts = "" if row["image_count"] is None else f" · {row['image_count']:,} files"
        typer.echo(f"{row['id']} · {row['status']} · {mode} · {row['folder']}{counts}")
