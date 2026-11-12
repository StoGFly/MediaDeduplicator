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
- Quarantine restoration workflows.
- CSV and HTML reports.

## Safety first

MediaDeduplicator is designed to protect your files.

- Scanning is read-only.
- No automatic permanent deletion.
- Quarantine operations require user confirmation.
- Restore functionality is planned.
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

Launch from the project environment with `python -m mediadedup.gui`.

Choose a recent folder in the editable path dropdown, or enter a new path. **Scan options → File extensions** lets you choose individual formats and stores the filter with the scan. Hide Scan Status to see compact progress along the bottom of the main window.

The Media preview panel supports video playback and opening the file in the default player. Tick copies to queue them for moving. **Move Status** shows the current file, bytes moved and issues. Successful moves clear their checkboxes, and failed copies stay queued for review.

- **Basic** finds exact SHA-256 duplicates in photos, videos, or both. Select the file types under **Include**. Advanced similarity searches photos.
- **Advanced** exposes the pHash agreement threshold and hash width for manual similarity review. The search compares every pair and may miss crops.

Both modes scan read-only. ORB controls remain part of the research roadmap.

**Review → Folder overlap** compares two separate folder trees using SHA-256. It shows how many files on each side match the other folder, the matched size, and the files that exist only on that side. Completed comparisons are saved locally.

Open **Scan Status** to see progress, elapsed time and totals. **Stop scan** saves a checkpoint. **Resume** checks for changed files and continues the saved scan. **Start fresh** starts a new history entry. Only one scan or move can run against the local database at a time. The toolbar groups Scan options, Review, Move and History. History shows related scans for the selected folder, including parent and nested folders. Move offers recent destinations and previews the scanned folder, chosen destination and full resulting paths.

The toolbar provides folder selection, scanning, scan history, filtering and file review controls. Desktop scans are recorded in the local `sql.db` under the MediaDeduplicator application data folder. History can reopen completed results with the original scan settings. Basic hashes only files that share a size. Advanced caches perceptual hashes in the database and reuses them on later scans when the file metadata and hash width match.

In Basic mode, **Keep by folder** selects visible exact groups with a single copy in the preferred folder or its subfolders. The Review column identifies the keeper. Use **Keep this file** to override it. **Move exact copies** previews the keeper, source, destination and total size before moving. The app rechecks both hashes and preserves relative paths at the destination. Choose a destination different from the scanned folder. The preview shows numbered filenames when the destination already contains a name.
