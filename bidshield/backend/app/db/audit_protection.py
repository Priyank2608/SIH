"""Layer 6 — Database-level append-only enforcement for the audit chain.

The hash chain in audit_service.py makes tampering DETECTABLE; these triggers
make it BLOCKED at the storage engine itself. The write flow inserts a row
with current_hash=NULL, flushes to obtain the row id used by the hash, then
sets the hash exactly once. The UPDATE trigger therefore enforces SEAL-ONCE
semantics: rows with a hash (every normal row) can never be modified, and no
row can ever be deleted. Even a buggy code path or an operator with the app's
DB role cannot silently rewrite history once an event is sealed.

Idempotent: safe to call on every startup and from tests.
"""
import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("bidshield.audit")

SQLITE_TRIGGERS = [
    # Seal-once: a hashed row is immutable. The only UPDATE ever permitted is
    # the initial NULL -> hash seal performed by audit_service at append time.
    """
    CREATE TRIGGER IF NOT EXISTS audit_logs_no_update
    BEFORE UPDATE ON audit_logs
    WHEN OLD.current_hash IS NOT NULL
    BEGIN
        SELECT RAISE(ABORT, 'audit_logs is append-only: sealed rows cannot be modified (tamper-evident chain policy)');
    END;
    """,
    # The seal must never CLEAR an existing hash (that would unlock the row).
    """
    CREATE TRIGGER IF NOT EXISTS audit_logs_no_unseal
    BEFORE UPDATE OF current_hash ON audit_logs
    WHEN OLD.current_hash IS NOT NULL AND NEW.current_hash IS NULL
    BEGIN
        SELECT RAISE(ABORT, 'audit_logs is append-only: unsealing a hashed event is blocked (tamper-evident chain policy)');
    END;
    """,
    # Block deletes — corrections are made by appending new events.
    """
    CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete
    BEFORE DELETE ON audit_logs
    BEGIN
        SELECT RAISE(ABORT, 'audit_logs is append-only: DELETE is blocked by tamper-evident chain policy');
    END;
    """,
]

POSTGRES_TRIGGERS = [
    """
    CREATE OR REPLACE FUNCTION bidshield_audit_no_update() RETURNS trigger AS $$
    BEGIN
        IF OLD.current_hash IS NOT NULL THEN
            RAISE EXCEPTION 'audit_logs is append-only: sealed rows cannot be modified (tamper-evident chain policy)';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """,
    """
    DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;
    CREATE TRIGGER audit_logs_no_update BEFORE UPDATE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION bidshield_audit_no_update();
    """,
    """
    CREATE OR REPLACE FUNCTION bidshield_audit_no_delete() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'audit_logs is append-only: DELETE is blocked by tamper-evident chain policy';
    END;
    $$ LANGUAGE plpgsql;
    """,
    """
    DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;
    CREATE TRIGGER audit_logs_no_delete BEFORE DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION bidshield_audit_no_delete();
    """,
]


def install_audit_protection(engine: Engine) -> None:
    """Install append-only triggers on audit_logs for the configured engine."""
    try:
        with engine.begin() as conn:
            if engine.dialect.name == "sqlite":
                for stmt in SQLITE_TRIGGERS:
                    conn.execute(text(stmt))
            elif engine.dialect.name == "postgresql":
                for stmt in POSTGRES_TRIGGERS:
                    conn.execute(text(stmt))
            else:
                logger.warning("No append-only trigger support for dialect %s", engine.dialect.name)
                return
        logger.info("Audit append-only protection installed on audit_logs")
    except Exception:
        # Never block boot on protection install; chain verification still
        # detects tampering, this only adds storage-level blocking.
        logger.exception("Failed to install audit append-only triggers")
