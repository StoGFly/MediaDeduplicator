"""Safety checks for the desktop recycle and restore workflow."""

from hashlib import sha256

import pytest

from mediadedup.move_copies import move_copy, restore_copy
from mediadedup.scan_history import ScanHistory


def test_recycle_and_restore_preserves_keeper_and_history(tmp_path):
    keeper = tmp_path / "keeper.jpg"
    copy = tmp_path / "copy.jpg"
    recycled = tmp_path / "recycle" / "copy.jpg"
    keeper.write_bytes(b"same photo")
    copy.write_bytes(keeper.read_bytes())
    history = ScanHistory(tmp_path / "sql.db")
    scan_id = history.start(tmp_path, False, 85, 8)
    entries = []

    def journal(digest):
        entries.append(history.begin_recycle(scan_id, copy, recycled, digest))

    move_copy(keeper, copy, recycled, on_moving=journal)
    history.complete_recycle(entries[0])
    assert keeper.read_bytes() == recycled.read_bytes()
    assert not copy.exists()
    assert history.moved_files(scan_id) == {str(copy): str(recycled)}

    entry, = history.recycle_entries()
    restore_copy(recycled, copy, entry["digest"])
    history.finish_restore(entry, copy)
    assert copy.read_bytes() == keeper.read_bytes()
    assert not recycled.exists()
    assert history.moved_files(scan_id) == {}
    assert history.recycle_entries()[0]["status"] == "restored"


def test_restore_refuses_occupied_path(tmp_path):
    recycled = tmp_path / "recycled.jpg"
    target = tmp_path / "original.jpg"
    recycled.write_bytes(b"photo")
    target.write_bytes(b"occupied")
    digest = sha256(recycled.read_bytes()).hexdigest()

    with pytest.raises(FileExistsError):
        restore_copy(recycled, target, digest)

    assert target.read_bytes() == b"occupied"
    assert recycled.read_bytes() == b"photo"


def test_restore_refuses_modified_recycle_file(tmp_path):
    recycled = tmp_path / "recycled.jpg"
    target = tmp_path / "original.jpg"
    recycled.write_bytes(b"changed")
    digest = sha256(b"original").hexdigest()

    with pytest.raises(ValueError, match="recorded hash"):
        restore_copy(recycled, target, digest)

    assert recycled.read_bytes() == b"changed"
    assert not target.exists()
