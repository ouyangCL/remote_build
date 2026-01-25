"""Add git_username and git_password fields to projects table

Revision ID: 010_add_git_username_password
Revises: 009
Create Date: 2026-01-24

This migration adds git_username and git_password fields to support basic authentication
for private Git servers, in addition to the existing OAuth2 token and SSH key methods.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_add_git_username_password'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    # Add git_username column for basic authentication
    op.add_column(
        'projects',
        sa.Column('git_username', sa.String(100), nullable=True)
    )

    # Add git_password column for basic authentication
    op.add_column(
        'projects',
        sa.Column('git_password', sa.String(255), nullable=True)
    )


def downgrade():
    # Remove git_password column
    op.drop_column('projects', 'git_password')

    # Remove git_username column
    op.drop_column('projects', 'git_username')
