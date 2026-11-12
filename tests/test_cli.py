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

def test_exact_media_scope_is_saved(tmp_path, monkeypatch):
    from mediadedup import scan_history

    history = scan_history.ScanHistory(tmp_path / "history.db")
    monkeypatch.setattr(scan_history, "ScanHistory", lambda: history)
    folder = tmp_path / "media"
    folder.mkdir()
    (folder / "a.mp4").write_bytes(b"matching")
    (folder / "b.mov").write_bytes(b"matching")
    (folder / "excluded.jpg").write_bytes(b"matching")

    result = runner.invoke(app, ["exact", str(folder), "--media", "videos", "--workers", "2"])

    assert result.exit_code == 0
    assert "2 files · 1 exact duplicate groups" in result.stdout
    assert "excluded.jpg" not in result.stdout
    entry, = history.list_scans()
    assert entry["scope"] == "videos"


def test_overlap_command_lists_unmatched_media(tmp_path, monkeypatch):
    from mediadedup import scan_history

    history = scan_history.ScanHistory(tmp_path / "history.db")
    monkeypatch.setattr(scan_history, "ScanHistory", lambda: history)
    first = tmp_path / "camera"
    second = tmp_path / "backup"
    first.mkdir()
    second.mkdir()
    (first / "original.jpg").write_bytes(b"same bytes")
    (second / "renamed.jpg").write_bytes(b"same bytes")
    (second / "only.mp4").write_bytes(b"extra file")

    result = runner.invoke(app, ["overlap", str(first), str(second)])

    assert result.exit_code == 0
    assert "1/2 matched · 1 only here" in result.stdout
    assert "only.mp4" in result.stdout
    assert len(history.recent_overlaps()) == 1
