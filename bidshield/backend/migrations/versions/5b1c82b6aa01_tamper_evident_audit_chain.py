"""Add audit chain fields and backfill existing audit events."""
from alembic import op
import hashlib
import json
import sqlalchemy as sa
from datetime import timezone

revision = "5b1c82b6aa01"
down_revision = "41c6f223efd2"
branch_labels = None
depends_on = None


def _genesis(tenant_id):
    return hashlib.sha256(f"BIDSHIELD_AUDIT_GENESIS_V1:{tenant_id}".encode("utf-8")).hexdigest()


def _event_hash(row, previous_hash):
    payload = {
        "id": row["id"], "tenant_id": row["tenant_id"], "user_id": row["user_id"],
        "username": row["username"], "action": row["action"], "entity_type": row["entity_type"],
        "entity_id": row["entity_id"], "ip_address": row["ip_address"],
        "details": row["details"] or {},
        "created_at": (row["created_at"].replace(tzinfo=timezone.utc)
                       if row["created_at"] and row["created_at"].tzinfo is None
                       else row["created_at"].astimezone(timezone.utc)
                       if row["created_at"] else None),
        "previous_hash": previous_hash,
    }
    if payload["created_at"] is not None:
        payload["created_at"] = payload["created_at"].isoformat()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    if "audit_logs" not in tables:
        return
    columns = {column["name"] for column in inspector.get_columns("audit_logs")}
    if "previous_hash" not in columns:
        op.add_column("audit_logs", sa.Column("previous_hash", sa.String(length=64), nullable=True))
    if "current_hash" not in columns:
        op.add_column("audit_logs", sa.Column("current_hash", sa.String(length=64), nullable=True))
    indexes = {index["name"] for index in sa.inspect(connection).get_indexes("audit_logs")}
    if "ix_audit_logs_previous_hash" not in indexes:
        op.create_index("ix_audit_logs_previous_hash", "audit_logs", ["previous_hash"])
    if "ix_audit_logs_current_hash" not in indexes:
        op.create_index("ix_audit_logs_current_hash", "audit_logs", ["current_hash"], unique=True)
    if "audit_chain_heads" not in set(sa.inspect(connection).get_table_names()):
        op.create_table(
            "audit_chain_heads",
            sa.Column("tenant_id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("last_event_id", sa.Integer(), nullable=True),
            sa.Column("last_hash", sa.String(length=64), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    audit = sa.table(
        "audit_logs",
        sa.column("id", sa.Integer), sa.column("tenant_id", sa.Integer),
        sa.column("user_id", sa.Integer), sa.column("username", sa.String),
        sa.column("action", sa.String), sa.column("entity_type", sa.String),
        sa.column("entity_id", sa.String), sa.column("ip_address", sa.String),
        sa.column("details", sa.JSON), sa.column("created_at", sa.DateTime),
        sa.column("previous_hash", sa.String), sa.column("current_hash", sa.String),
    )
    rows = connection.execute(sa.select(audit).order_by(audit.c.tenant_id, audit.c.id)).mappings().all()
    previous_by_tenant = {}
    latest_by_tenant = {}
    for original in rows:
        row = dict(original)
        tenant_id = row["tenant_id"] if row["tenant_id"] is not None else 1
        if row["tenant_id"] is None:
            connection.execute(audit.update().where(audit.c.id == row["id"]).values(tenant_id=tenant_id))
            row["tenant_id"] = tenant_id
        previous = previous_by_tenant.setdefault(tenant_id, _genesis(tenant_id))
        current = _event_hash(row, previous)
        connection.execute(audit.update().where(audit.c.id == row["id"]).values(previous_hash=previous, current_hash=current))
        previous_by_tenant[tenant_id] = current
        latest_by_tenant[tenant_id] = (row["id"], current)

    heads = sa.table("audit_chain_heads", sa.column("tenant_id", sa.Integer),
                     sa.column("last_event_id", sa.Integer), sa.column("last_hash", sa.String),
                     sa.column("updated_at", sa.DateTime))
    from datetime import datetime, timezone
    for tenant_id, (event_id, digest) in latest_by_tenant.items():
        connection.execute(heads.delete().where(heads.c.tenant_id == tenant_id))
        connection.execute(heads.insert().values(tenant_id=tenant_id, last_event_id=event_id,
            last_hash=digest, updated_at=datetime.now(timezone.utc)))


def downgrade():
    connection = op.get_bind()
    if "audit_chain_heads" in set(sa.inspect(connection).get_table_names()):
        op.drop_table("audit_chain_heads")
    if "audit_logs" in set(sa.inspect(connection).get_table_names()):
        indexes = {index["name"] for index in sa.inspect(connection).get_indexes("audit_logs")}
        if "ix_audit_logs_current_hash" in indexes:
            op.drop_index("ix_audit_logs_current_hash", table_name="audit_logs")
        if "ix_audit_logs_previous_hash" in indexes:
            op.drop_index("ix_audit_logs_previous_hash", table_name="audit_logs")
        with op.batch_alter_table("audit_logs") as batch_op:
            columns = {column["name"] for column in sa.inspect(connection).get_columns("audit_logs")}
            if "current_hash" in columns:
                batch_op.drop_column("current_hash")
            if "previous_hash" in columns:
                batch_op.drop_column("previous_hash")
