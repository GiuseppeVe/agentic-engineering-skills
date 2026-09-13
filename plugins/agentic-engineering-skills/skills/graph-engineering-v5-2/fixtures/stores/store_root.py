from __future__ import annotations

from pathlib import Path


def create_store_root(store_root: Path) -> Path:
    """Create an empty durable-store root for a test."""
    store_root.mkdir(parents=True)
    return store_root
