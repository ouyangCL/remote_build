"""Add health check configuration to projects table

Revision ID: 007_add_health_check
Revises: 006_add_git_ssh_key
Create Date: 2026-01-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_add_health_check'
down_revision: Union[str, None] = '006_add_git_ssh_key'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add health check columns to projects table."""
    # Add health check configuration columns
    op.add_column(
        'projects',
        sa.Column('health_check_enabled', sa.Boolean, nullable=False, server_default='false')
    )
    op.add_column(
        'projects',
        sa.Column('health_check_type', sa.String(20), nullable=False, server_default='http')
    )
    op.add_column(
        'projects',
        sa.Column('health_check_url', sa.String(500), nullable=True)
    )
    op.add_column(
        'projects',
        sa.Column('health_check_port', sa.Integer, nullable=True)
    )
    op.add_column(
        'projects',
        sa.Column('health_check_command', sa.Text, nullable=True)
    )
    op.add_column(
        'projects',
        sa.Column('health_check_timeout', sa.Integer, nullable=False, server_default='30')
    )
    op.add_column(
        'projects',
        sa.Column('health_check_retries', sa.Integer, nullable=False, server_default='3')
    )
    op.add_column(
        'projects',
        sa.Column('health_check_interval', sa.Integer, nullable=False, server_default='5')
    )

    # Create index for health_check_enabled for faster queries
    op.create_index(
        'ix_projects_health_check_enabled',
        'projects',
        ['health_check_enabled']
    )


def downgrade() -> None:
    """Remove health check columns from projects table."""
    # Drop index
    op.drop_index('ix_projects_health_check_enabled', table_name='projects')

    # Remove health check configuration columns
    op.drop_column('projects', 'health_check_interval')
    op.drop_column('projects', 'health_check_retries')
    op.drop_column('projects', 'health_check_timeout')
    op.drop_column('projects', 'health_check_command')
    op.drop_column('projects', 'health_check_port')
    op.drop_column('projects', 'health_check_url')
    op.drop_column('projects', 'health_check_type')
    op.drop_column('projects', 'health_check_enabled')
