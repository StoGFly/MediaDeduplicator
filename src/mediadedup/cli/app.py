"""MediaDeduplicator command-line interface."""

import os
import stat
from pathlib import Path

import typer

from mediadedup.detectors.exact import find_exact_duplicates

app = typer.Typer(
    name="mediadedup",
    help="Find duplicate and similar images, videos and audio files.",
    no_args_is_help=True,
)


def is_hidden(path: Path) -> bool:
    """Check whether a file or directory is hidden."""
    try:
        if path.name.startswith("."):
            return True

        attributes = path.stat(follow_symlinks=False).st_file_attributes
        return bool(attributes & stat.FILE_ATTRIBUTE_HIDDEN)
    except OSError:
        return False


def discover_files(root: Path) -> list[Path]:
    """Recursively discover files, excluding hidden items and symlinks."""
    discovered = []

    for current_dir, directories, filenames in os.walk(
        root,
        followlinks=False,
    ):
        current_path = Path(current_dir)

        directories[:] = [
            name
            for name in directories
            if not is_hidden(current_path / name)
            and not (current_path / name).is_symlink()
        ]

        for filename in filenames:
            file_path = current_path / filename

            if file_path.is_symlink() or is_hidden(file_path):
                continue

            if file_path.is_file():
                discovered.append(file_path)

    return discovered


@app.callback()
def main():
    """MediaDeduplicator application."""


@app.command()
def version():
    """Display the application version."""
    from mediadedup import __version__

    typer.echo(f"MediaDeduplicator {__version__}")


@app.command()
def scan(
    folder: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Folder to scan recursively.",
    ),
):
    """Find files with identical contents using SHA-256."""
    typer.echo(f"Scanning: {folder}")

    files = discover_files(folder)
    typer.echo(f"Files discovered: {len(files)}")

    try:
        duplicate_groups = find_exact_duplicates(files)
    except OSError as error:
        typer.echo(
            f"Scan aborted because a file could not be read: {error}",
            err=True,
        )
        raise typer.Exit(code=1)

    if not duplicate_groups:
        typer.echo("No exact duplicates found.")
        return

    wasted_bytes = 0

    typer.echo(f"\nDuplicate groups found: {len(duplicate_groups)}")

    for group_number, group in enumerate(duplicate_groups, start=1):
        typer.echo(f"\nGroup {group_number}:")

        for path in group:
            typer.echo(f"  {path}")

        try:
            wasted_bytes += sum(path.stat().st_size for path in group[1:])
        except OSError as error:
            typer.echo(
                f"Could not calculate duplicate file sizes: {error}",
                err=True,
            )
            raise typer.Exit(code=1)

    wasted_mb = wasted_bytes / (1024 * 1024)

    typer.echo("\nScan summary:")
    typer.echo(f"  Files scanned: {len(files)}")
    typer.echo(f"  Duplicate groups: {len(duplicate_groups)}")
    typer.echo(f"  Redundant data: {wasted_mb:.2f} MiB")
    typer.echo("\nNo files were changed.")


if __name__ == "__main__":
    app()