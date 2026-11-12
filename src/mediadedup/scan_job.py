"""Resumable desktop scanning with cooperative stop points."""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
from time import monotonic

from PySide6.QtCore import QThread, Signal

from mediadedup.cli.app import iter_files
from mediadedup.core.hashing import file_fingerprint, sha256_file
from mediadedup.detectors.image import iter_hash_pair_rows
from mediadedup.media_formats import IMAGE_EXTENSIONS, scan_extensions


class ScanStopped(Exception):
    pass


class Scan(QThread):
    completed = Signal(object, int, int)
    failed = Signal(str)
    stopped = Signal(int)
    progress = Signal(object)

    def __init__(self, folder, similarity, threshold, hash_size, history, parent,
                 resume_id=None, scope="photos", extensions=None):
        super().__init__(parent)
        self.folder = folder
        self.similarity = similarity
        self.threshold = threshold
        self.hash_size = hash_size
        self.history = history
        self.resume_id = resume_id
        self.scope = "photos" if similarity else scope
        available = scan_extensions(self.scope, self.similarity)
        self.extensions = available if extensions is None else available.intersection(extensions)
        self.last_update = 0.0
        self.photo_count = 0
        self.video_count = 0
        self.total_bytes = 0

    @property
    def file_count(self):
        return self.photo_count + self.video_count

    def report(self, phase, done=0, total=0, *, force=False, byte_progress=None):
        now = monotonic()
        if force or now - self.last_update >= 0.15:
            self.last_update = now
            self.progress.emit((
                phase, done, total, self.photo_count, self.video_count,
                self.total_bytes, byte_progress,
            ))
        if self.isInterruptionRequested():
            raise ScanStopped

    def inventory(self):
        paths = {}
        self.report("Finding files", force=True)
        for path in iter_files(self.folder):
            extension = path.suffix.lower()
            if extension in self.extensions:
                photo = extension in IMAGE_EXTENSIONS
                signature = list(file_fingerprint(path))
                paths[path] = signature
                self.photo_count += photo
                self.video_count += not photo
                self.total_bytes += signature[2]
            self.report("Finding files")
        return dict(sorted(paths.items()))

    def digest(self, path, signature, saved, calculate):
        key = str(path)
        cached = saved.get(key)
        if cached is not None and cached[0] == signature:
            return cached[1]
        digest = calculate(path)
        if list(file_fingerprint(path)) != signature:
            raise OSError(f"File changed during the scan: {path}")
        saved[key] = [signature, digest]
        return digest

    def exact_matches(self, paths, signatures, saved):
        sizes = Counter(signatures[path][2] for path in paths)
        candidates = [path for path in paths if sizes[signatures[path][2]] > 1]
        phase = "Checking exact hashes"
        total = len(candidates)
        total_bytes = sum(signatures[path][2] for path in candidates)
        completed_bytes = 0
        self.report(phase, 0, total, force=True, byte_progress=(0, total_bytes))
        groups = defaultdict(list)
        for index, path in enumerate(candidates, 1):
            current_bytes = 0

            def on_chunk(size):
                nonlocal current_bytes
                current_bytes += size
                self.report(
                    phase, index - 1, total,
                    byte_progress=(completed_bytes + current_bytes, total_bytes),
                )

            digest = self.digest(
                path, signatures[path], saved,
                lambda file: sha256_file(file, on_chunk=on_chunk),
            )
            groups[digest].append(path)
            completed_bytes += signatures[path][2]
            self.report(phase, index, total, byte_progress=(completed_bytes, total_bytes))
        return [group for group in groups.values() if len(group) > 1]

    def similar_matches(self, paths, signatures, checkpoint):
        phase = "Hashing photos"
        self.report(phase, 0, len(paths), force=True)
        saved = checkpoint.setdefault("phash", {})
        digests = []
        with self.history.cached_phash() as hash_image:
            for index, path in enumerate(paths, 1):
                digest = self.digest(
                    path, signatures[path], saved,
                    lambda file: hash_image(file, self.hash_size),
                )
                digests.append(digest)
                self.report(phase, index, len(paths))

        identity = hashlib.sha256(
            json.dumps(list(zip(map(str, paths), digests))).encode("utf-8")
        ).hexdigest()
        if checkpoint.get("pair_key") != identity:
            checkpoint.update(pair_key=identity, pair_row=0, pairs=[])
        pairs = checkpoint["pairs"]
        start = checkpoint["pair_row"]
        phase = "Comparing photo pairs"
        count = len(paths)
        total_pairs = count * (count - 1) // 2
        self.report(phase, start * (2 * count - start - 1) // 2, total_pairs, force=True)
        for row, matches in iter_hash_pair_rows(
            [int(digest, 16) for digest in digests], self.threshold,
            self.hash_size * self.hash_size, start,
        ):
            pairs.extend(matches)
            checkpoint["pair_row"] = row + 1
            completed_rows = row + 1
            compared = completed_rows * (2 * count - completed_rows - 1) // 2
            self.report(phase, compared, total_pairs)

        endpoints = sorted({paths[index] for a, b, _, _ in pairs for index in (a, b)})
        exact = {
            path: group[0]
            for group in self.exact_matches(endpoints, signatures, checkpoint["exact"])
            for path in group
        }
        return [
            (f"{score:.2f}% pHash agreement", [paths[a], paths[b]])
            for a, b, _, score in sorted(pairs, key=lambda pair: pair[3], reverse=True)
            if exact.get(paths[a], paths[a]) != exact.get(paths[b], paths[b])
        ]

    def run(self):
        scan_id = None
        try:
            if self.resume_id is None:
                checkpoint = {}
                scan_id = self.history.start(
                    self.folder, self.similarity, self.threshold, self.hash_size, self.scope, self.extensions
                )
            else:
                checkpoint = self.history.resume(self.resume_id)
                scan_id = self.resume_id
            checkpoint.setdefault("exact", {})

            try:
                signatures = self.inventory()
                paths = list(signatures)
                if self.similarity:
                    groups = self.similar_matches(paths, signatures, checkpoint)
                else:
                    groups = [
                        (f"Exact group {index} ({len(group)} files)", group)
                        for index, group in enumerate(
                            self.exact_matches(paths, signatures, checkpoint["exact"]), 1
                        )
                    ]
                self.report("Saving results", force=True)
                results = [
                    (title, [(path, signatures[path][2]) for path in group])
                    for title, group in groups
                ]
            except ScanStopped:
                self.history.stop(scan_id, checkpoint, self.file_count)
                self.stopped.emit(scan_id)
                return

            self.history.complete(scan_id, results, self.file_count)
            self.completed.emit(results, self.file_count, scan_id)
        except (OSError, ValueError, sqlite3.Error) as error:
            message = str(error)
            if scan_id is not None:
                try:
                    self.history.fail(scan_id, message)
                except (OSError, sqlite3.Error) as history_error:
                    message += f"\nScan history could not be updated: {history_error}"
            self.failed.emit(message)
