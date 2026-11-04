"""Tests for the MediaDeduplicator command-line interface."""

from typer.testing import CliRunner

from mediadedup import __version__
from mediadedup.cli.app import app


runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert f"MediaDeduplicator {__version__}" in result.stdout


def test_help_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Find duplicate and similar images" in result.stdout
    assert "version" in result.stdout
    assert "scan" in result.stdout


def test_scan_finds_duplicates(tmp_path):
    folder = tmp_path / "media"
    folder.mkdir()

    file_a = folder / "photo_a.jpg"
    file_b = folder / "photo_b.jpg"

    file_a.write_bytes(b"same photo data")
    file_b.write_bytes(b"same photo data")

    result = runner.invoke(app, ["scan", str(folder)])

    assert result.exit_code == 0
    assert "Files discovered: 2" in result.stdout
    assert "Duplicate groups found: 1" in result.stdout
    assert "No files were changed." in result.stdout


def test_scan_empty_folder(tmp_path):
    folder = tmp_path / "empty"
    folder.mkdir()

    result = runner.invoke(app, ["scan", str(folder)])

    assert result.exit_code == 0
    assert "Files discovered: 0" in result.stdout
    assert "No exact duplicates found." in result.stdout


def test_scan_skips_hidden_files_and_directories(tmp_path):
    folder = tmp_path / "media"
    folder.mkdir()

    visible = folder / "visible.jpg"
    visible.write_bytes(b"visible data")

    hidden_file = folder / ".hidden.jpg"
    hidden_file.write_bytes(b"hidden data")

    hidden_folder = folder / ".private"
    hidden_folder.mkdir()
    (hidden_folder / "secret.jpg").write_bytes(b"secret data")

    result = runner.invoke(app, ["scan", str(folder)])

    assert result.exit_code == 0
    assert "Files discovered: 1" in result.stdout