"""Local SQLite history for desktop scans."""

from contextlib import closing, contextmanager
from datetime import datetime
import json
from pathlib import Path
import sqlite3

from platformdirs import user_data_path

from mediadedup.detectors.image import perceptual_hash
from mediadedup.core.hashing import file_fingerprint


DATABASE_PATH = user_data_path("MediaDeduplicator", appauthor=False) / "sql.db"


class ScanHistory:
    def __init__(self, path=DATABASE_PATH):
        self.path = path

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS gui_scans (
                    id INTEGER PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    folder TEXT NOT NULL,
                    similarity INTEGER NOT NULL,
                    threshold REAL,
                    hash_size INTEGER,
                    status TEXT NOT NULL,
                    image_count INTEGER,
                    match_count INTEGER,
                    results TEXT,
                    error TEXT
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS gui_moves (
                    scan_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    PRIMARY KEY (scan_id, source)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS gui_phash_v1 (
                    path TEXT NOT NULL,
                    hash_size INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    PRIMARY KEY (path, hash_size)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS gui_scan_checkpoints (
                    scan_id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS gui_move_destinations (
                    path TEXT PRIMARY KEY,
                    used_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS gui_scan_scope (
                    scan_id INTEGER PRIMARY KEY,
                    scope TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS gui_folder_overlaps (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    folder_a TEXT NOT NULL,
                    folder_b TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    results TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS gui_scan_extensions (
                    scan_id INTEGER PRIMARY KEY,
                    extensions TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS gui_recycle (
                    id INTEGER PRIMARY KEY,
                    scan_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    restored_to TEXT
                )
            """)
        except sqlite3.Error:
            connection.close()
            raise
        return connection

    def start(self, folder, similarity, threshold, hash_size, scope="photos", extensions=None):
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute("""
                INSERT INTO gui_scans (started_at, folder, similarity, threshold, hash_size, status)
                VALUES (?, ?, ?, ?, ?, 'started')
            """, (
                datetime.now().astimezone().isoformat(timespec="seconds"),
                str(folder), similarity, threshold if similarity else None,
                hash_size if similarity else None,
            ))
            scan_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO gui_scan_scope (scan_id, scope) VALUES (?, ?)",
                (scan_id, scope),
            )
            if extensions is not None:
                connection.execute(
                    "INSERT INTO gui_scan_extensions (scan_id, extensions) VALUES (?, ?)",
                    (scan_id, json.dumps(sorted(extensions))),
                )
            return scan_id

    def complete(self, scan_id, groups, image_count):
        results = [
            (label, [(str(path), size) for path, size in files])
            for label, files in groups
        ]
        with closing(self.connect()) as connection, connection:
            connection.execute("""
                UPDATE gui_scans
                SET status = 'completed', image_count = ?, match_count = ?, results = ?
                WHERE id = ?
            """, (image_count, len(groups), json.dumps(results), scan_id))
            connection.execute("DELETE FROM gui_scan_checkpoints WHERE scan_id = ?", (scan_id,))

    def stop(self, scan_id, checkpoint, image_count):
        with closing(self.connect()) as connection, connection:
            connection.execute("""
                INSERT OR REPLACE INTO gui_scan_checkpoints (scan_id, data) VALUES (?, ?)
            """, (scan_id, json.dumps(checkpoint)))
            connection.execute("""
                UPDATE gui_scans SET status = 'incomplete', image_count = ?, error = NULL
                WHERE id = ?
            """, (image_count, scan_id))

    def resume(self, scan_id):
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute("""
                UPDATE gui_scans SET status = 'started', error = NULL
                WHERE id = ? AND status = 'incomplete'
            """, (scan_id,))
            if not cursor.rowcount:
                raise ValueError("This scan is no longer available to resume.")
            saved = connection.execute(
                "SELECT data FROM gui_scan_checkpoints WHERE scan_id = ?", (scan_id,)
            ).fetchone()
            if saved is None:
                raise ValueError("This scan has no saved checkpoint.")
            return json.loads(saved["data"])

    def scan_settings(self, scan_id):
        with closing(self.connect()) as connection:
            row = connection.execute("""
                SELECT folder, similarity, threshold, hash_size, status,
                       COALESCE(gui_scan_scope.scope, 'photos') AS scope,
                       gui_scan_extensions.extensions
                FROM gui_scans LEFT JOIN gui_scan_scope ON gui_scans.id = gui_scan_scope.scan_id
                LEFT JOIN gui_scan_extensions ON gui_scans.id = gui_scan_extensions.scan_id WHERE id = ?
            """, (scan_id,)).fetchone()
        if row is None:
            raise ValueError("The scan was not found in History.")
        return row

    def record_destination(self, folder):
        with closing(self.connect()) as connection, connection:
            connection.execute("""
                INSERT OR REPLACE INTO gui_move_destinations (path, used_at) VALUES (?, ?)
            """, (str(folder), datetime.now().astimezone().isoformat()))

    def recent_destinations(self):
        with closing(self.connect()) as connection:
            return [row["path"] for row in connection.execute("""
                SELECT path FROM gui_move_destinations ORDER BY used_at DESC LIMIT 10
            """)]

    def fail(self, scan_id, error):
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "UPDATE gui_scans SET status = 'failed', error = ? WHERE id = ?",
                (error, scan_id),
            )

    def recent_scan_folders(self):
        with closing(self.connect()) as connection:
            return [row["folder"] for row in connection.execute("""
                SELECT folder FROM gui_scans GROUP BY folder COLLATE NOCASE
                ORDER BY MAX(id) DESC LIMIT 20
            """)]

    def list_scans(self):
        with closing(self.connect()) as connection:
            return connection.execute("""
                SELECT id, started_at, folder, similarity, status, image_count, match_count, error,
                       COALESCE(gui_scan_scope.scope, 'photos') AS scope
                FROM gui_scans LEFT JOIN gui_scan_scope ON gui_scans.id = gui_scan_scope.scan_id ORDER BY id DESC
            """).fetchall()

    def load(self, scan_id):
        with closing(self.connect()) as connection:
            scan = connection.execute("""
                SELECT folder, similarity, threshold, hash_size, image_count, results,
                       COALESCE(gui_scan_scope.scope, 'photos') AS scope,
                       gui_scan_extensions.extensions
                FROM gui_scans LEFT JOIN gui_scan_scope ON gui_scans.id = gui_scan_scope.scan_id
                LEFT JOIN gui_scan_extensions ON gui_scans.id = gui_scan_extensions.scan_id WHERE id = ? AND status = 'completed'
            """, (scan_id,)).fetchone()
        if scan is None:
            raise ValueError("This scan has no saved results.")
        groups = [
            (label, [(Path(path), size) for path, size in files])
            for label, files in json.loads(scan["results"])
        ]
        return scan, groups

    def record_move(self, scan_id, source, destination):
        with closing(self.connect()) as connection, connection:
            connection.execute("""
                INSERT OR REPLACE INTO gui_moves (scan_id, source, destination)
                VALUES (?, ?, ?)
            """, (scan_id, str(source), str(destination)))

    def moved_files(self, scan_id):
        with closing(self.connect()) as connection:
            return dict(connection.execute("""
                SELECT source, destination FROM gui_moves WHERE scan_id = ?
            """, (scan_id,)).fetchall())

    @contextmanager
    def cached_phash(self):
        with closing(self.connect()) as connection:
            pending = []

            def hash_image(path, hash_size):
                before = file_fingerprint(path)
                signature = repr(before)
                row = connection.execute("""
                    SELECT digest FROM gui_phash_v1
                    WHERE path = ? AND hash_size = ? AND fingerprint = ?
                """, (str(path), hash_size, signature)).fetchone()
                if row is not None:
                    return row["digest"]

                digest = str(perceptual_hash(path, hash_size))
                if file_fingerprint(path) == before:
                    pending.append((str(path), hash_size, signature, digest))
                return digest

            yield hash_image
            with connection:
                connection.executemany("""
                    INSERT INTO gui_phash_v1 (path, hash_size, fingerprint, digest)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(path, hash_size) DO UPDATE
                    SET fingerprint = excluded.fingerprint, digest = excluded.digest
                """, pending)

    def save_overlap(self, first, second, scope, results):
        with closing(self.connect()) as connection, connection:
            connection.execute("""
                INSERT INTO gui_folder_overlaps (created_at, folder_a, folder_b, scope, results)
                VALUES (?, ?, ?, ?, ?)
            """, (datetime.now().astimezone().isoformat(), str(first), str(second),
                  scope, json.dumps(results)))

    def recent_overlaps(self):
        with closing(self.connect()) as connection:
            return connection.execute("""
                SELECT id, created_at, folder_a, folder_b, scope
                FROM gui_folder_overlaps ORDER BY id DESC LIMIT 20
            """).fetchall()

    def load_overlap(self, comparison_id):
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT results FROM gui_folder_overlaps WHERE id = ?", (comparison_id,)
            ).fetchone()
        if row is None:
            raise ValueError("This comparison was not found.")
        return json.loads(row["results"])

    def begin_recycle(self, scan_id, source, destination, digest):
        with closing(self.connect()) as connection, connection:
            row = connection.execute("""
                INSERT INTO gui_recycle (scan_id, source, destination, digest, status)
                VALUES (?, ?, ?, ?, 'pending')
            """, (scan_id, str(source), str(destination), digest))
            return row.lastrowid

    def complete_recycle(self, entry_id):
        with closing(self.connect()) as connection, connection:
            connection.execute("UPDATE gui_recycle SET status = 'recycled' WHERE id = ?", (entry_id,))
            connection.execute("""
                INSERT OR REPLACE INTO gui_moves (scan_id, source, destination)
                SELECT scan_id, source, destination FROM gui_recycle WHERE id = ?
            """, (entry_id,))

    def recycle_entries(self):
        with closing(self.connect()) as connection:
            return connection.execute("""
                SELECT id, scan_id, source, destination, digest, status, restored_to
                FROM gui_recycle ORDER BY id DESC
            """).fetchall()

    def finish_restore(self, entry, destination):
        source = entry["source"]
        target = str(destination)
        with closing(self.connect()) as connection, connection:
            connection.execute("""
                UPDATE gui_recycle SET status = 'restored', restored_to = ? WHERE id = ?
            """, (target, entry["id"]))
            if Path(source) == destination:
                connection.execute(
                    "DELETE FROM gui_moves WHERE scan_id = ? AND source = ?",
                    (entry["scan_id"], source),
                )
            else:
                connection.execute("""
                    INSERT OR REPLACE INTO gui_moves (scan_id, source, destination) VALUES (?, ?, ?)
                """, (entry["scan_id"], source, target))
