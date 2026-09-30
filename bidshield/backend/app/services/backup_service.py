"""Layer 4 — Snapshot & Backup Vault.

Every snapshot is a self-contained single-file copy of the live database plus
a SHA-256 checksum stored alongside it. Snapshots are written to a vault
directory OUTSIDE the live database's own directory so a wedged writer on the
live path never blocks a backup, and every file is chmod'd 0600.

Snapshot triggers:
  1. Application startup (survives: crash during a deployment)
  2. Fixed schedule (default every 180 minutes)
  3. Admin on-demand endpoint (POST /api/v1/admin/backups)
  4. Instant out-of-band request from a Layer 2 anomaly (debounced)

There is no Celery/worker process in this stack, so the schedule runs on a
daemon thread started with the app — the smallest viable substitute. A snapshot
on the same disk does NOT survive disk loss: OPERATIONS MUST copy the vault
off-host (see README §Backup Vault).
"""
import hashlib
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger("bidshield.vault")

_scheduler_lock = threading.Lock()
_scheduler_thread: Optional[threading.Thread] = None


def _live_db_path() -> Optional[str]:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return None  # postgres: use pg_dump (documented limitation, see README)


def _verify_checksum(path: str) -> bool:
    checksum_path = path + ".sha256"
    if not os.path.exists(checksum_path):
        return False
    with open(checksum_path, "r", encoding="utf-8") as fh:
        expected = fh.read().split()[0].strip().lower()
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected


def _write_snapshot_file(dest_path: str) -> str:
    """Produce a consistent snapshot file and return its SHA-256."""
    db_path = _live_db_path()
    if db_path:
        # SQLite online-backup API: safe against concurrent writers, and it
        # never touches the live file's lock in a blocking way.
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(dest_path)
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
            src.close()
    else:
        # PostgreSQL deployments: shell out to pg_dump. Not exercised by the
        # demo suite (SQLite); documented as the production path.
        import subprocess
        from urllib.parse import urlparse
        parsed = urlparse(settings.database_url)
        subprocess.run(
            ["pg_dump", "--format=custom", "--file", dest_path,
             "--dbname", f"postgresql://{parsed.username}:****@{parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}"],
            check=True,
            env={**os.environ, "PGPASSWORD": parsed.password or ""},
        )
    os.chmod(dest_path, 0o600)  # owner read/write only — vault files are secrets

    digest = hashlib.sha256()
    with open(dest_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    checksum = digest.hexdigest()

    checksum_path = dest_path + ".sha256"
    with open(checksum_path, "w", encoding="utf-8") as fh:
        fh.write(f"{checksum}  {os.path.basename(dest_path)}\n")
    os.chmod(checksum_path, 0o600)
    return checksum


def take_snapshot(reason: str = "MANUAL") -> Tuple[str, Dict[str, Any]]:
    """Create a checksummed snapshot in the vault. Returns (path, metadata)."""
    os.makedirs(settings.backup_vault_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")[:-3]
    dest = os.path.join(settings.backup_vault_dir, f"bidshield-{stamp}-{reason.lower()}.snapshot")
    checksum = _write_snapshot_file(dest)
    meta = {
        "path": dest,
        "filename": os.path.basename(dest),
        "reason": reason,
        "sha256": checksum,
        "size_bytes": os.path.getsize(dest),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("Vault snapshot (%s): %s sha256=%s", reason, dest, checksum[:16])
    _prune_old_snapshots()
    return dest, meta


def list_snapshots(verify: bool = True) -> List[Dict[str, Any]]:
    """List vault snapshots; verifies each SHA-256 when requested."""
    vault = settings.backup_vault_dir
    out: List[Dict[str, Any]] = []
    if not os.path.isdir(vault):
        return out
    for name in sorted(os.listdir(vault), reverse=True):
        if not name.endswith(".snapshot"):
            continue
        path = os.path.join(vault, name)
        entry: Dict[str, Any] = {
            "filename": name,
            "size_bytes": os.path.getsize(path),
            "created_at": datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat(),
        }
        checksum_path = path + ".sha256"
        if os.path.exists(checksum_path):
            with open(checksum_path, "r", encoding="utf-8") as fh:
                entry["sha256"] = fh.read().split()[0]
        if verify:
            entry["checksum_ok"] = _verify_checksum(path)
        out.append(entry)
    return out


def restore_snapshot(filename: str) -> str:
    """Verify then restore a vault snapshot over the live database.

    Returns the path restored. The live file is replaced atomically via
    os.replace so a crash mid-restore cannot corrupt both copies.
    """
    if os.sep in filename or "/" in filename or ".." in filename:
        raise ValueError("Invalid snapshot filename")
    path = os.path.abspath(os.path.join(settings.backup_vault_dir, filename))
    vault_root = os.path.abspath(settings.backup_vault_dir)
    if not path.startswith(vault_root + os.sep) or not os.path.exists(path):
        raise FileNotFoundError("Snapshot not found in vault")
    if not _verify_checksum(path):
        raise ValueError("Checksum verification failed — snapshot is corrupt or tampered")

    db_path = _live_db_path()
    if not db_path:
        raise NotImplementedError("Automated restore is supported for SQLite; restore PostgreSQL snapshots with pg_restore")

    tmp = path + ".restore-tmp"
    src = sqlite3.connect(path)
    dst = sqlite3.connect(tmp)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()
    os.replace(tmp, os.path.abspath(db_path))
    logger.warning("Vault snapshot restored over live database: %s", filename)
    return path


def _prune_old_snapshots() -> None:
    """Keep the newest N snapshots (checksum sidecars count with their file)."""
    keep = max(3, settings.backup_keep_count)
    vault = settings.backup_vault_dir
    snaps = sorted(
        (n for n in os.listdir(vault) if n.endswith(".snapshot")),
        reverse=True,
    )
    for name in snaps[keep:]:
        for suffix in ("", ".sha256"):
            try:
                os.remove(os.path.join(vault, name + suffix))
            except OSError:
                pass


def start_scheduler() -> None:
    """Start the periodic snapshot daemon thread (no-op if already running).

    Interval is settings.backup_interval_minutes; zero/negative disables.
    """
    global _scheduler_thread
    if not settings.backup_enabled or settings.backup_interval_minutes <= 0:
        return
    with _scheduler_lock:
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            return

        def _loop():
            interval = settings.backup_interval_minutes * 60
            while True:
                time.sleep(interval)
                try:
                    take_snapshot(reason="SCHEDULED")
                except Exception:
                    logger.exception("Scheduled vault snapshot failed")

        import time
        _scheduler_thread = threading.Thread(target=_loop, name="bidshield-backup-vault", daemon=True)
        _scheduler_thread.start()


def startup_snapshot() -> Optional[str]:
    """Take the on-startup snapshot; failures must not block boot."""
    if not settings.backup_enabled:
        return None
    try:
        path, _ = take_snapshot(reason="STARTUP")
        return path
    except Exception:
        logger.exception("Startup vault snapshot failed (boot continues)")
        return None
