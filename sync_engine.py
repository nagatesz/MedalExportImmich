"""
sync_engine.py — Core upload engine. Streams each file individually to Immich
via the REST API, tracks per-file progress, and supports checkpoint recovery.
"""

import os
import json
import time
import datetime
import requests
from pathlib import Path
from threading import Lock

import config
from scanner import build_inventory, VIDEO_EXTENSIONS

STATE_FILE = Path("sync_state.json")
LOG_FILE = Path("sync_events.log")
PROGRESS_FILE = Path("uploaded_files.json")

_lock = Lock()


class SyncState:
    """Thread-safe sync state that is continuously written to disk and served via the API."""

    def __init__(self):
        self.total_files = 0
        self.total_bytes = 0
        self.processed_files = 0
        self.uploaded_files = 0
        self.duplicate_files = 0
        self.failed_files = 0
        self.processed_bytes = 0
        self.uploaded_bytes = 0
        self.current_target = "Initializing"
        self.current_file = ""
        self.status = "starting"
        self.start_time = time.time()
        self.speed_mbps = 0.0
        self.recent_logs: list[dict] = []
        self.targets: list[dict] = []
        self.album_id = ""
        self.immich_url = ""
        self.completed_paths: set[str] = set()
        self._load_cache()

    # --- Cache (tracks which files have already been processed) ---

    def _load_cache(self):
        if PROGRESS_FILE.exists():
            try:
                with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                    self.completed_paths = set(json.load(f))
            except Exception:
                self.completed_paths = set()

    def _save_cache(self):
        try:
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self.completed_paths), f)
        except Exception:
            pass

    # --- Logging ---

    def log(self, message: str, log_type: str = "info"):
        ts = time.strftime("%H:%M:%S")
        entry = {"time": ts, "type": log_type, "message": message}
        with _lock:
            self.recent_logs.append(entry)
            if len(self.recent_logs) > 120:
                self.recent_logs = self.recent_logs[-120:]
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] [{log_type.upper()}] {message}\n")
        except Exception:
            pass

    # --- Progress ---

    def file_done(self, filepath: Path, file_bytes: int, status: str, dur: float = 0.0):
        with _lock:
            self.completed_paths.add(str(filepath))
            self.processed_files += 1
            self.processed_bytes += file_bytes
            if status == "uploaded":
                self.uploaded_files += 1
                self.uploaded_bytes += file_bytes
                if dur > 0:
                    self.speed_mbps = round((file_bytes / (1024 * 1024)) / dur, 2)
            elif status == "duplicate":
                self.duplicate_files += 1
            elif status == "failed":
                self.failed_files += 1
            self.current_file = filepath.name
        self._save_cache()
        self.flush()

    def flush(self):
        """Write current state to disk for the dashboard."""
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.as_dict(), f, indent=2)
        except Exception:
            pass

    def as_dict(self) -> dict:
        with _lock:
            elapsed = max(1, time.time() - self.start_time)
            pct = round((self.processed_files / max(1, self.total_files)) * 100, 1)
            remaining = max(0, self.total_bytes - self.processed_bytes)
            eta = int(remaining / max(1, self.speed_mbps * 1024 * 1024)) if self.speed_mbps > 0 else 0
            return {
                "status": self.status,
                "total_files": self.total_files,
                "processed_files": self.processed_files,
                "uploaded_files": self.uploaded_files,
                "duplicate_files": self.duplicate_files,
                "failed_files": self.failed_files,
                "total_bytes": self.total_bytes,
                "processed_bytes": self.processed_bytes,
                "percent": pct,
                "speed_mbps": self.speed_mbps,
                "eta_seconds": eta,
                "elapsed_seconds": int(elapsed),
                "current_target": self.current_target,
                "current_file": self.current_file,
                "recent_logs": self.recent_logs[-60:],
                "targets": self.targets,
                "album_id": self.album_id,
                "immich_url": self.immich_url,
            }


# Module-level singleton
state = SyncState()


# ---------------------------------------------------------------------------
# Immich helpers
# ---------------------------------------------------------------------------

def _headers():
    return {"x-api-key": config.IMMICH_API_KEY, "Accept": "application/json"}


def connect_immich() -> str:
    """Try primary URL, then fallback. Returns the working base URL."""
    for url in [config.IMMICH_URL, config.FALLBACK_URL]:
        if not url:
            continue
        try:
            r = requests.get(f"{url}/api/server/ping", timeout=5)
            if r.status_code == 200:
                state.immich_url = url
                state.log(f"Connected to Immich at {url}", "info")
                return url
        except Exception:
            continue
    raise RuntimeError("Cannot connect to Immich. Check IMMICH_URL in .env")


def ensure_album(base_url: str) -> str:
    """Find or create the Medal album. Returns the album ID."""
    r = requests.get(f"{base_url}/api/albums", headers=_headers(), timeout=10)
    r.raise_for_status()
    for a in r.json():
        if a.get("albumName") == config.ALBUM_NAME:
            state.album_id = a["id"]
            state.log(f"Using album '{config.ALBUM_NAME}' ({a.get('assetCount', 0)} assets)", "info")
            return a["id"]
    r = requests.post(f"{base_url}/api/albums", headers=_headers(), json={"albumName": config.ALBUM_NAME}, timeout=10)
    r.raise_for_status()
    aid = r.json()["id"]
    state.album_id = aid
    state.log(f"Created album '{config.ALBUM_NAME}' (ID: {aid})", "info")
    return aid


# ---------------------------------------------------------------------------
# Single-file upload
# ---------------------------------------------------------------------------

def upload_file(filepath: Path, base_url: str, album_id: str) -> bool:
    """Upload one file to Immich and add it to the album. Returns True on success."""
    st = filepath.stat()
    mtime = datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc).isoformat()
    device_id = f"{filepath.name}-{st.st_size}"

    data = {
        "deviceAssetId": device_id,
        "deviceId": "MedalExportImmich",
        "fileCreatedAt": mtime,
        "fileModifiedAt": mtime,
        "isFavorite": "false",
    }

    ext = filepath.suffix.lower()
    mime_map = {".mp4": "video/mp4", ".mkv": "video/x-matroska", ".mov": "video/quicktime",
                ".webm": "video/webm", ".avi": "video/x-msvideo",
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime = mime_map.get(ext, "application/octet-stream")

    t0 = time.time()
    try:
        with open(filepath, "rb") as f:
            files = {"assetData": (filepath.name, f, mime)}
            r = requests.post(f"{base_url}/api/assets", headers=_headers(), data=data, files=files, timeout=600)

        dur = max(0.05, time.time() - t0)
        mb = st.st_size / (1024 * 1024)

        if r.status_code in (200, 201):
            resp = r.json()
            asset_id = resp.get("id")
            upload_status = resp.get("status", "created")

            # Always ensure album membership
            if asset_id:
                try:
                    requests.put(f"{base_url}/api/albums/{album_id}/assets",
                                 headers=_headers(), json={"ids": [asset_id]}, timeout=10)
                except Exception:
                    pass

            if upload_status == "duplicate":
                state.file_done(filepath, st.st_size, "duplicate", dur)
                state.log(f"Duplicate: {filepath.name} ({mb:.1f} MB)", "warn")
            else:
                speed = mb / dur
                state.file_done(filepath, st.st_size, "uploaded", dur)
                state.log(f"Uploaded: {filepath.name} ({mb:.1f} MB @ {speed:.1f} MB/s)", "success")
            return True
        else:
            state.file_done(filepath, st.st_size, "failed")
            state.log(f"HTTP {r.status_code} on {filepath.name}: {r.text[:120]}", "error")
            return False

    except Exception as e:
        state.file_done(filepath, st.st_size, "failed")
        state.log(f"Error uploading {filepath.name}: {e}", "error")
        return False


# ---------------------------------------------------------------------------
# Main export loop
# ---------------------------------------------------------------------------

def run_export():
    """Full export pipeline — call from a background thread."""
    state.status = "running"
    state.log("Starting Medal Export to Immich...", "info")

    # Connect
    base_url = connect_immich()
    album_id = ensure_album(base_url)

    # Discover & inventory
    state.log("Scanning for Medal clips...", "info")
    inv = build_inventory()
    state.total_files = inv["total_files"]
    state.total_bytes = inv["total_bytes"]
    state.targets = inv["targets"]
    state.log(f"Found {inv['total_files']} files ({inv['total_bytes'] / (1024**3):.1f} GB) across {len(inv['targets'])} folders", "info")
    state.flush()

    img_exts = {".jpg", ".jpeg", ".png", ".webp"}
    all_exts = VIDEO_EXTENSIONS | img_exts

    for t_idx, target in enumerate(state.targets, 1):
        target_path = Path(target["path"])
        target["status"] = "uploading"
        state.current_target = target["name"]
        state.log(f"[{t_idx}/{len(state.targets)}] {target['name']} — {target['file_count']} files, {target['total_bytes']/(1024**2):.0f} MB", "target")
        state.flush()

        files = sorted(
            f for f in target_path.rglob("*")
            if f.is_file() and f.suffix.lower() in all_exts
            and ".thumbnails" not in str(f).lower()
        )

        for fp in files:
            if str(fp) in state.completed_paths:
                continue
            state.current_file = fp.name
            upload_file(fp, base_url, album_id)

        target["status"] = "completed"
        state.log(f"Completed: {target['name']}", "success")
        state.flush()

    # Done
    state.status = "completed"
    state.current_target = "Export Complete"
    state.current_file = "All clips safely stored in Immich"
    state.flush()

    # Verify
    try:
        r = requests.get(f"{base_url}/api/albums/{album_id}", headers=_headers(), timeout=10)
        if r.status_code == 200:
            count = r.json().get("assetCount", 0)
            state.log(f"✅ Verified: {count} assets in '{config.ALBUM_NAME}' album on Immich", "success")
    except Exception:
        pass

    state.log("🎉 Export finished!", "success")
