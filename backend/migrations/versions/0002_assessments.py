"""manual assessments: equipment description, recorded_by, recommendations, idempotency key

Revision ID: 0002
Revises: 0001

Existing rows are kept. All new columns are nullable.
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("predictions") as batch:
        batch.add_column(sa.Column("equipment_description", sa.String(120), nullable=True))
        batch.add_column(sa.Column("recorded_by", sa.String(64), nullable=True))
        batch.add_column(sa.Column("recommendation_summary", sa.String(500), nullable=True))
        batch.add_column(sa.Column("ruleset_version", sa.String(40), nullable=True))
        batch.add_column(sa.Column("recommendations", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("idempotency_key", sa.String(64), nullable=True))
        batch.add_column(sa.Column("request_hash", sa.String(64), nullable=True))
        batch.create_index("ix_predictions_idempotency_key", ["idempotency_key"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("predictions") as batch:
        batch.drop_index("ix_predictions_idempotency_key")
        for col in ("request_hash", "idempotency_key", "recommendations", "ruleset_version", "recommendation_summary", "recorded_by", "equipment_description"):
            batch.drop_column(col)
