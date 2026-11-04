"""Allow MediaDeduplicator to be run as a Python module."""

from mediadedup.cli.app import app

if __name__ == "__main__":
    app()