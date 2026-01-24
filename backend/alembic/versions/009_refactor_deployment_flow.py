"""Refactor deployment flow

Revision ID: 009
Revises: 008_add_deployment_progress
Create Date: 2026-01-24

This migration refactors the deployment flow to:
1. Add upload_path field to projects table for storing package upload path
2. Rename deploy_script_path to restart_script_path in projects table
3. Remove deploy_path field from servers table (deployment path is now per-project)

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add upload_path column to projects table
    op.add_column(
        'projects',
        sa.Column('upload_path', sa.String(255), nullable=False, server_default='')
    )

    # Step 2: Rename deploy_script_path to restart_script_path
    with op.batch_alter_table('projects') as batch_op:
        batch_op.alter_column(
            'deploy_script_path',
            new_column_name='restart_script_path'
        )

    # Step 3: Drop deploy_path column from servers table
    op.drop_column('servers', 'deploy_path')


def downgrade():
    # Revert Step 3: Add back deploy_path column to servers table
    op.add_column(
        'servers',
        sa.Column('deploy_path', sa.String(255), nullable=False, server_default='/opt/app')
    )

    # Revert Step 2: Rename restart_script_path back to deploy_script_path
    with op.batch_alter_table('projects') as batch_op:
        batch_op.alter_column(
            'restart_script_path',
            new_column_name='deploy_script_path'
        )

    # Revert Step 1: Remove upload_path column from projects table
    op.drop_column('projects', 'upload_path')
