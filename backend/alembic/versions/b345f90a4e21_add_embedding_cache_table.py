"""add embedding_cache table

Revision ID: b345f90a4e21
Revises: 4ce3a577d477
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b345f90a4e21'
down_revision: Union[str, Sequence[str], None] = '4ce3a577d477'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'embedding_cache',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('vector', sa.JSON(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('embedding_cache')
