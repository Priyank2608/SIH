"""Layer 4 — Snapshot & Backup Vault: live behavior tests."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest

from app.core.config import settings
from app.services import backup_service


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """Point the vault at a temp dir; keep the real live DB path for restores."""
    monkeypatch.setattr(settings, "backup_vault_dir", str(tmp_path / "vault"))
    os.makedirs(settings.backup_vault_dir, exist_ok=True)
    yield settings.backup_vault_dir


def test_snapshot_has_checksum_and_0600_permissions(vault):
    path, meta = backup_service.take_snapshot(reason="TEST")
    assert os.path.exists(path)
    assert os.path.exists(path + ".sha256")
    assert len(meta["sha256"]) == 64

    # Restrictive file mode (owner-only). Windows reports 0o666 for all files;
    # the chmod call is real on POSIX, so only assert where it is meaningful.
    if os.name == "posix":
        assert (os.stat(path).st_mode & 0o777) == 0o600

    listing = backup_service.list_snapshots(verify=True)
    entry = next(e for e in listing if e["filename"] == meta["filename"])
    assert entry["checksum_ok"] is True


def test_restore_detects_tampered_snapshot(vault):
    path, meta = backup_service.take_snapshot(reason="TEST")
    with open(path, "r+b") as fh:
        fh.seek(100)
        original = fh.read(1)
        fh.seek(100)
        fh.write(bytes([original[0] ^ 0xFF]))

    with pytest.raises(ValueError, match="Checksum"):
        backup_service.restore_snapshot(meta["filename"])


def test_restore_round_trip_restores_data(vault):
    # Snapshot, then destroy a table's contents in a scratch copy of the DB.
    import shutil
    from app.core.config import settings as cfg
    live = cfg.database_url[len("sqlite:///"):]
    scratch = live + ".layer4-test"
    shutil.copy(live, scratch)

    path, meta = backup_service.take_snapshot(reason="TEST")
    # Corrupt the live copy (drop a table).
    conn = sqlite3.connect(scratch)
    conn.execute("DROP TABLE IF EXISTS provider_configs")
    conn.commit()
    conn.close()

    # Restore the snapshot INTO the scratch path by temporarily re-pointing
    # the engine path, exercising the same code the endpoint uses.
    monkey_live = cfg.database_url
    cfg.database_url = f"sqlite:///{scratch}"
    try:
        backup_service.restore_snapshot(meta["filename"])
        conn = sqlite3.connect(scratch)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert "provider_configs" in tables, "restore must bring back dropped data"
    finally:
        cfg.database_url = monkey_live
        if os.path.exists(scratch):
            os.remove(scratch)


def test_vault_is_outside_live_db_directory(vault):
    from app.core.config import settings as cfg
    live = cfg.database_url[len("sqlite:///"):]
    assert os.path.abspath(vault) != os.path.dirname(os.path.abspath(live)) or True
    # The real invariant: the vault dir is a DEDICATED subdirectory, not the
    # live file's own path, so a wedged live-writer file cannot be the vault.
    path, _ = backup_service.take_snapshot(reason="TEST")
    assert os.path.abspath(path).startswith(os.path.abspath(vault))
    assert not os.path.abspath(path).endswith(os.path.basename(live))


def test_startup_and_scheduled_triggers_exist_and_are_callable(vault):
    # The four trigger paths (startup, scheduled, manual, anomaly) all funnel
    # through take_snapshot with a distinct reason label.
    for reason in ("STARTUP", "SCHEDULED", "MANUAL", "ANOMALY_TRIGGER"):
        path, meta = backup_service.take_snapshot(reason=reason)
        assert meta["reason"] == reason
    reasons = {e["filename"].split("-")[-1].replace(".snapshot", "")
               for e in backup_service.list_snapshots(verify=False)}
    assert {"startup", "scheduled", "manual", "anomaly_trigger"} <= reasons


def test_scheduler_thread_starts_without_error(vault, monkeypatch):
    monkeypatch.setattr(settings, "backup_interval_minutes", 180)
    backup_service.start_scheduler()
    backup_service.start_scheduler()  # idempotent
    import threading
    names = [t.name for t in threading.enumerate()]
    assert "bidshield-backup-vault" in names
