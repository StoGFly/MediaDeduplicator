# MediaDeduplicator

A Windows desktop and command-line application for finding duplicate and similar media files.

**Status:** Early development

## Planned features

- Image, video and audio scanning.
- Exact duplicate detection using SHA-256.
- Perceptual image similarity detection.
- Video comparison using sampled frames.
- Audio fingerprint comparison.
- Optional AI-assisted similarity detection.
- Desktop GUI built with PySide6.
- Command-line interface.
- SQLite-based scan history and indexing.
- Safe quarantine and restore functionality.
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