# MediaDeduplicator

A Windows desktop and command-line application for finding exact copies of photos and videos and visually similar photos.

**Status:** Early development

## Available now

- Desktop GUI and command-line exact duplicate scanning.
- Read-only SHA-256 scans for photos and videos in the GUI.
- Experimental photo similarity with pHash.
- SQLite scan history, resumable scans, and saved folder comparisons.
- Exact-copy review and verified moves to a user-selected destination.

## Planned features

- Optional AI-assisted similarity detection.
- Batch restoration and folder merge.
- CSV and HTML reports.

## Safety first

MediaDeduplicator is designed to protect your files.

- Scanning is read-only.
- No automatic permanent deletion.
- Moving or recycling exact copies requires user confirmation.
- Restore verifies the recycled file and preserves existing files.
- Duplicate decisions retain their supporting evidence.

## Requirements

- Windows 10/11 64-bit.
- Python 3.12 or newer.

## Development setup

Clone the repository, then:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Desktop app

Launch from the project environment with `python -m mediadedup.gui`. The window remembers its size, position, maximized state and preview split.

### Scan and compare

- **Basic** finds exact SHA-256 duplicates in photos, videos, or both. **Scan options → File extensions** sets the formats. **Hash workers** sets concurrent reads to 1, 2, 4 or 8, with four by default.
- **Advanced** finds experimental pHash similarity candidates in photos. The search can miss crops. pHash and exact scan history are stored locally in `sql.db`.
- **Scan Status** shows the exact-hashing rate and estimated time remaining. Hide it to see progress in the bottom bar. Stop saves a checkpoint and Resume rechecks files that changed.
- **History** reopens results and shows related folder scans. **Review → Folder overlap** compares exact coverage and lists files with no match in the other folder.

### Review and move

- Select a keeper manually from a file's right-click menu, or use **Move → Keep by folder** or **Keep by filename pattern**. The filename rule flags choices that could drop descriptive text.
- Use checkboxes and **Show queued only** to review a move batch. The queue shows checked copies, copies hidden by the filter and total size. Right-click results to copy paths, filter by folder or update visible checkboxes.
- The move preview sorts by path and lets you remove individual rows before confirming. The app rechecks copies against their keepers. Move Status reports queued, moved, remaining and failed sizes.
- **Recycle checked copies** moves verified extras to a folder you choose. **History → Recycle Folder** restores one copy at a time. If its original path is occupied, choose an unused path. The app verifies the recorded SHA-256 before restoring.
- **Media preview** supports photos and video. Video playback includes volume, mute, seeking and ten-second skips. The app remembers volume and mute.

## Command line

Run these from the project environment. Use `--help` after any command for its options.

```powershell
python -m mediadedup exact "D:\Photos" --media both --workers 4
python -m mediadedup similar "D:\Photos" --threshold 90 --hash-size 8
python -m mediadedup overlap "D:\Photos" "D:\Backup" --media videos
python -m mediadedup history --limit 20
```

`exact` and `similar` write scan history and share the operation lock with the desktop app. `overlap` saves its folder comparison locally. The original `scan` command checks exact contents across all discovered files. Use the desktop app for recycling and restoring copies.
