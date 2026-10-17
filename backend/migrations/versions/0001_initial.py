"""initial tables: upload_batches and predictions

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("filename", sa.String(100), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
    )
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("upload_batches.id"), nullable=True),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("record_id", sa.String(64), nullable=True),
        sa.Column("motor_id", sa.String(64), nullable=True),
        sa.Column("measured_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("predicted_condition", sa.String(64), nullable=False),
        sa.Column("predicted_class_id", sa.Integer(), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("provisional_label_provenance", sa.Boolean(), nullable=False),
        sa.Column("demonstration_only", sa.Boolean(), nullable=False),
        sa.Column("input_readings", sa.JSON(), nullable=True),
    )
    op.create_index("ix_predictions_motor_id", "predictions", ["motor_id"])
    op.create_index("ix_predictions_created_at", "predictions", ["created_at"])
    op.create_index("ix_predictions_measured_at", "predictions", ["measured_at"])
    op.create_index("ix_predictions_batch_id", "predictions", ["batch_id"])
    op.create_index("ix_predictions_motor_created", "predictions", ["motor_id", "created_at"])


def downgrade() -> None:
    for name in ("ix_predictions_motor_created", "ix_predictions_batch_id", "ix_predictions_measured_at",
                 "ix_predictions_created_at", "ix_predictions_motor_id"):
        op.drop_index(name, table_name="predictions")
    op.drop_table("predictions")
    op.drop_table("upload_batches")
