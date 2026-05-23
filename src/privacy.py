from __future__ import annotations

from pathlib import Path

from src.paths import STORAGE_DIR

PRIVATE_PATTERNS = ["*.json", "*.csv", "*.db", "*.sqlite", "*.parquet"]


def ensure_private_storage() -> None:
    """Create the local storage directory without creating tracked user data files."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    gitkeep = STORAGE_DIR / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")


def private_storage_summary() -> dict[str, object]:
    """Return a small summary of local private files for UI warnings."""
    ensure_private_storage()
    files: list[Path] = []
    for pattern in PRIVATE_PATTERNS:
        files.extend(STORAGE_DIR.glob(pattern))
    files = sorted(set(files))
    return {
        "storage_dir": str(STORAGE_DIR),
        "private_file_count": len(files),
        "private_files": [p.name for p in files],
    }
