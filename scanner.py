"""
scanner.py — Auto-discovers all Medal clips across common locations and builds
a structured inventory grouped by game / folder.
"""

import json
from pathlib import Path
from config import MEDAL_DIR

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi"}

# Common Medal install locations on Windows
SEARCH_ROOTS = [
    MEDAL_DIR,
    Path("C:/Medal"),
    Path.home() / "Videos" / "Medal",
]


def discover_medal_root() -> Path:
    """Return the first Medal root that actually contains clips."""
    for root in SEARCH_ROOTS:
        if root.exists() and (root / "Clips").exists():
            return root
    # Fallback to configured
    return MEDAL_DIR


def build_inventory(medal_root: Path | None = None) -> dict:
    """
    Scan the Medal directory tree and return a structured inventory.

    Returns dict with keys: total_files, total_bytes, targets[]
    Each target: {name, game, path, file_count, total_bytes}
    """
    if medal_root is None:
        medal_root = discover_medal_root()

    targets = []

    # 1. Clips/<game>
    clips_dir = medal_root / "Clips"
    if clips_dir.exists():
        for game_dir in sorted(clips_dir.iterdir()):
            if game_dir.is_dir():
                files = _video_files(game_dir)
                if files:
                    targets.append(_make_target(f"Clips / {game_dir.name}", game_dir.name, game_dir, files))

    # 2. Edits
    edits_dir = medal_root / "Edits"
    if edits_dir.exists():
        files = _video_files(edits_dir)
        if files:
            targets.append(_make_target("Edits", "Edits", edits_dir, files))

    # 3. Imports
    imports_dir = medal_root / "Imports"
    if imports_dir.exists():
        files = _video_files(imports_dir)
        if files:
            targets.append(_make_target("Imports", "Imports", imports_dir, files))

    # 4. Editor renders
    editor_dir = medal_root / "editor"
    if editor_dir.exists():
        render_dir = editor_dir / "render"
        search = render_dir if render_dir.exists() else editor_dir
        files = _video_files(search, recurse=True)
        if files:
            targets.append(_make_target("Editor Renders", "Editor", search, files))

    # 5. Screenshots (images)
    screenshots_dir = medal_root / "Screenshots"
    if screenshots_dir.exists():
        img_exts = {".jpg", ".jpeg", ".png", ".webp"}
        files = [f for f in screenshots_dir.rglob("*") if f.is_file() and f.suffix.lower() in img_exts]
        if files:
            targets.append(_make_target("Screenshots", "Screenshots", screenshots_dir, files))

    total_files = sum(t["file_count"] for t in targets)
    total_bytes = sum(t["total_bytes"] for t in targets)

    return {
        "medal_root": str(medal_root),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "targets": targets,
    }


def _video_files(directory: Path, recurse: bool = False) -> list[Path]:
    """Collect video files from a directory."""
    pattern = directory.rglob("*") if recurse else directory.iterdir()
    return [
        f for f in pattern
        if f.is_file()
        and f.suffix.lower() in VIDEO_EXTENSIONS
        and ".thumbnails" not in str(f).lower()
        and "\\temp\\" not in str(f).lower()
    ]


def _make_target(name: str, game: str, path: Path, files: list[Path]) -> dict:
    total_bytes = sum(f.stat().st_size for f in files)
    return {
        "name": name,
        "game": game,
        "path": str(path),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "status": "queued",
    }


if __name__ == "__main__":
    inv = build_inventory()
    print(f"Medal root: {inv['medal_root']}")
    print(f"Total files: {inv['total_files']}")
    print(f"Total size:  {inv['total_bytes'] / (1024**3):.2f} GB")
    print()
    for t in inv["targets"]:
        print(f"  {t['name']:<40} {t['file_count']:>5} files  {t['total_bytes']/(1024**2):>10.1f} MB")
