"""Создать таблицу измерений."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "metrics",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=False),
        sa.Column("memory_used_bytes", sa.BigInteger(), nullable=False),
        sa.Column("memory_total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("disk_used_bytes", sa.BigInteger(), nullable=False),
        sa.Column("disk_total_bytes", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("cpu_percent >= 0 AND cpu_percent <= 100", name="ck_metrics_cpu"),
        sa.CheckConstraint("memory_used_bytes >= 0 AND memory_total_bytes > 0 AND memory_used_bytes <= memory_total_bytes", name="ck_metrics_memory"),
        sa.CheckConstraint("disk_used_bytes >= 0 AND disk_total_bytes > 0 AND disk_used_bytes <= disk_total_bytes", name="ck_metrics_disk"),
    )
    op.create_index("ix_metrics_agent_collected_id", "metrics", ["agent_id", "collected_at", "id"])


def downgrade():
    op.drop_index("ix_metrics_agent_collected_id", table_name="metrics")
    op.drop_table("metrics")
