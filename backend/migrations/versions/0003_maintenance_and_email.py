"""maintenance follow-up cases, their update log, and e-mailed report log

Revision ID: 0003
Revises: 0002

Only NEW tables are added. The predictions table is not touched, so existing assessments and their results are unchanged.
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maintenance_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("predictions.id"), nullable=False, unique=True),
        sa.Column("motor_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(48), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_maintenance_cases_status", "maintenance_cases", ["status"])
    op.create_index("ix_maintenance_cases_motor_id", "maintenance_cases", ["motor_id"])
    op.create_table(
        "maintenance_updates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("maintenance_cases.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("from_status", sa.String(48), nullable=True),
        sa.Column("to_status", sa.String(48), nullable=False),
        sa.Column("updated_by", sa.String(64), nullable=True),
        sa.Column("responsible_engineer", sa.String(64), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("fault_found", sa.String(1000), nullable=True),
        sa.Column("actions_performed", sa.String(1000), nullable=True),
        sa.Column("parts_notes", sa.String(500), nullable=True),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("verification_outcome", sa.String(24), nullable=True),
        sa.Column("reassessment_date", sa.Date(), nullable=True),
        sa.Column("reassessment_assessment_id", sa.Integer(), sa.ForeignKey("predictions.id"), nullable=True),
    )
    op.create_index("ix_maintenance_updates_case_id", "maintenance_updates", ["case_id"])
    op.create_index("ix_maintenance_updates_reassessment", "maintenance_updates", ["reassessment_assessment_id"], unique=True)
    op.create_table(
        "report_emails",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("predictions.id"), nullable=False),
        sa.Column("recipient", sa.String(254), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("error_summary", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_report_emails_assessment_id", "report_emails", ["assessment_id"])
    op.create_index("ix_report_emails_created_at", "report_emails", ["created_at"])


def downgrade() -> None:
    op.drop_table("report_emails")
    op.drop_table("maintenance_updates")
    op.drop_table("maintenance_cases")
