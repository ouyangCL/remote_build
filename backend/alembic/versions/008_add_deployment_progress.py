"""Add deployment progress tracking

Revision ID: 008
Revises: 007
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007_add_health_check'
branch_labels = None
depends_on = None


def upgrade():
    # Add progress column to deployments table
    op.add_column(
        'deployments',
        sa.Column('progress', sa.Integer, nullable=False, server_default='0')
    )

    # Add current_step column to deployments table
    op.add_column(
        'deployments',
        sa.Column('current_step', sa.String(50), nullable=True)
    )

    # Add total_steps column to deployments table
    op.add_column(
        'deployments',
        sa.Column('total_steps', sa.Integer, nullable=False, server_default='5')
    )


def downgrade():
    # Drop columns
    op.drop_column('deployments', 'total_steps')
    op.drop_column('deployments', 'current_step')
    op.drop_column('deployments', 'progress')
