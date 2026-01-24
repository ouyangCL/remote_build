"""add restart_only_script_path

Revision ID: 011_add_restart_only_script_path
Revises: 010_add_git_username_password
Create Date: 2025-01-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011_add_restart_only_script_path'
down_revision = '010_add_git_username_password'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'projects',
        sa.Column(
            'restart_only_script_path',
            sa.String(255),
            nullable=True,
            default=None
        )
    )


def downgrade():
    op.drop_column('projects', 'restart_only_script_path')
