"""add auto_install fields

Revision ID: 012
Revises: 011
Create Date: 2026-01-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    # Add install_script column (optional, 500 chars)
    op.add_column('projects', sa.Column('install_script', sa.String(500), nullable=True))

    # Add auto_install column (defaults to True)
    op.add_column('projects', sa.Column('auto_install', sa.Boolean(), nullable=False, server_default='1'))


def downgrade():
    op.drop_column('projects', 'auto_install')
    op.drop_column('projects', 'install_script')
