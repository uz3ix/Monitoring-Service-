"""Uptime, усреднение CPU, скорости сети/дисков и выбранные службы."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

RATE_COLUMNS = (
    "cpu_max_percent", "sample_duration_seconds",
    "network_receive_bytes_per_second", "network_send_bytes_per_second",
    "disk_read_bytes_per_second", "disk_write_bytes_per_second",
)


def upgrade():
    # Nullable сохраняет совместимость со старыми измерениями и агентами.
    for name in RATE_COLUMNS:
        op.add_column("metrics", sa.Column(name, sa.Float(), nullable=True))
    op.add_column("metrics", sa.Column("uptime_seconds", sa.BigInteger(), nullable=True))
    op.add_column("metrics", sa.Column("services", postgresql.JSONB(), nullable=True))


def downgrade():
    for name in (*RATE_COLUMNS, "uptime_seconds", "services"):
        op.drop_column("metrics", name)
