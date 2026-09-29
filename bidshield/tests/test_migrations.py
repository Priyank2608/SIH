import os
import subprocess
import sys
from uuid import uuid4
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1] / "backend"


def _alembic(database_url: str, *args: str):
    env = os.environ.copy()
    env["BIDSHIELD_DATABASE_URL"] = database_url
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND,
                          env=env, capture_output=True, text=True, check=True)


def test_clean_upgrade_downgrade_upgrade_preserves_data():
    name = f"migration_test_{uuid4().hex}.db"
    db_path = BACKEND / "storage" / name
    database_url = f"sqlite:///{db_path.resolve().as_posix()}"
    engine = None
    try:
        _alembic(database_url, "upgrade", "head")
        engine = create_engine(database_url)
        table_names = set(inspect(engine).get_table_names())
        assert {"tenants", "tenders", "bidders", "audit_logs", "audit_chain_heads"} <= table_names
        assert {"previous_hash", "current_hash"} <= {c["name"] for c in inspect(engine).get_columns("audit_logs")}
        assert "signature_data" in {c["name"] for c in inspect(engine).get_columns("users")}
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO tenants (code,name,created_at) VALUES ('MIG','Migration tenant',CURRENT_TIMESTAMP)"))
        engine.dispose()

        _alembic(database_url, "downgrade", "-1")
        engine = create_engine(database_url)
        assert "signature_data" not in {c["name"] for c in inspect(engine).get_columns("users")}
        assert "previous_hash" in {c["name"] for c in inspect(engine).get_columns("audit_logs")}
        engine.dispose()

        _alembic(database_url, "downgrade", "-1")
        engine = create_engine(database_url)
        assert "previous_hash" not in {c["name"] for c in inspect(engine).get_columns("audit_logs")}
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM tenants WHERE code='MIG'")).scalar_one() == 1
        engine.dispose()

        _alembic(database_url, "upgrade", "head")
        engine = create_engine(database_url)
        assert "current_hash" in {c["name"] for c in inspect(engine).get_columns("audit_logs")}
        assert "signature_data" in {c["name"] for c in inspect(engine).get_columns("users")}
        engine.dispose()
    finally:
        if engine is not None:
            engine.dispose()
        if db_path.exists():
            db_path.unlink()
