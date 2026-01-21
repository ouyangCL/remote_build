"""Add environment isolation

Revision ID: 002_add_environment_isolation
Revises: 001_add_audit_logs
Create Date: 2026-01-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_environment_isolation'
down_revision: Union[str, None] = '001_add_audit_logs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add environment column to projects, server_groups, and deployments tables."""

    # Step 1: Add nullable environment columns
    op.add_column('projects', sa.Column('environment', sa.String(20), nullable=True))
    op.add_column('server_groups', sa.Column('environment', sa.String(20), nullable=True))
    op.add_column('deployments', sa.Column('environment', sa.String(20), nullable=True))

    # Step 2: Set default value 'development' for all existing records
    op.execute("UPDATE projects SET environment = 'development' WHERE environment IS NULL")
    op.execute("UPDATE server_groups SET environment = 'development' WHERE environment IS NULL")
    op.execute("UPDATE deployments SET environment = 'development' WHERE environment IS NULL")

    # Step 3: Make columns NOT NULL
    op.alter_column('projects', 'environment', nullable=False)
    op.alter_column('server_groups', 'environment', nullable=False)
    op.alter_column('deployments', 'environment', nullable=False)

    # Step 4: Create indexes for efficient filtering
    op.create_index(op.f('ix_projects_environment'), 'projects', ['environment'], unique=False)
    op.create_index(op.f('ix_server_groups_environment'), 'server_groups', ['environment'], unique=False)
    op.create_index(op.f('ix_deployments_environment'), 'deployments', ['environment'], unique=False)


def downgrade() -> None:
    """Remove environment column from projects, server_groups, and deployments tables."""

    # Drop indexes first
    op.drop_index(op.f('ix_deployments_environment'), table_name='deployments')
    op.drop_index(op.f('ix_server_groups_environment'), table_name='server_groups')
    op.drop_index(op.f('ix_projects_environment'), table_name='projects')

    # Drop columns
    op.drop_column('deployments', 'environment')
    op.drop_column('server_groups', 'environment')
    op.drop_column('projects', 'environment')
