"""Filename rules for choosing a keeper within exact duplicate groups."""

from collections import Counter
from pathlib import Path
import re

from PySide6.QtCore import QThread, Signal

from mediadedup.cli.app import iter_files


DATE_DOTS = "YYYY-MM-DD HH.mm.ss"
DATE_COMPACT = "YYYYMMDD_HHMMSS"
PATTERNS = (
    (DATE_DOTS, re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}\.\d{2}\.\d{2}(?!\d)")),
    (DATE_COMPACT, re.compile(r"^\d{8}_\d{6}(?!\d)")),
)
COPY_SUFFIX = re.compile(r"(?:[ _-]+copy(?:[ _-]*\(\d+\)|[ _-]+\d+)?|[ _-]*\(\d+\)|-\d+)$", re.I)
OTHER = "Other filenames"


def filename_parts(path):
    stem = path.stem
    for style, pattern in PATTERNS:
        match = pattern.match(stem)
        if match:
            suffix = COPY_SUFFIX.sub("", stem[match.end():])
            return style, normalize_description(suffix)
    return OTHER, normalize_description(COPY_SUFFIX.sub("", stem))


def normalize_description(text):
    return " ".join(text.strip(" ._-").replace("_", " ").casefold().split())


def winning_style(counts):
    ranked = [(style, counts.get(style, 0)) for style, _ in PATTERNS]
    ranked.sort(key=lambda entry: entry[1], reverse=True)
    first, second = ranked
    return first[0] if first[1] > second[1] else None


def filename_keeper(paths, folder, style, preferred_folder=None):
    """Return a keeper and reason, or a review reason if the choice is ambiguous."""
    parts = {path: filename_parts(path) for path in paths}
    preferred = [
        path for path, (pattern, _) in parts.items()
        if pattern == style and path.is_relative_to(folder)
    ]
    descriptions = {description for _, description in parts.values() if description}
    if len(preferred) == 1:
        keeper = preferred[0]
        if descriptions <= {parts[keeper][1]}:
            return keeper, "Filename pattern"

    if len(descriptions) == 1 and preferred_folder is not None:
        description = next(iter(descriptions))
        named = [path for path, (_, suffix) in parts.items() if suffix == description]
        choices = [
            path for path in named
            if path.is_relative_to(preferred_folder) and path.is_relative_to(folder)
        ]
        if len(named) > 1 and len(choices) == 1:
            return choices[0], "Description and preferred folder"

    if len(descriptions) > 1 or (
        descriptions and (not preferred or any(parts[path][1] not in descriptions for path in preferred))
    ):
        return None, "Descriptive filename"
    if not preferred:
        return None, "No file in preferred style"
    return None, "Multiple files in preferred style"


class CountFilenamePatterns(QThread):
    counted = Signal(object)
    failed = Signal(str)

    def __init__(self, folder, extensions, parent):
        super().__init__(parent)
        self.folder = folder
        self.extensions = extensions

    def run(self):
        def unreadable(error):
            raise error

        counts = Counter()
        try:
            for path in iter_files(self.folder, on_error=unreadable):
                if path.suffix.lower() in self.extensions:
                    style, _ = filename_parts(path)
                    counts[style] += 1
        except OSError as error:
            self.failed.emit(str(error))
        else:
            self.counted.emit(counts)
