"""add product embedding_source_text column

Revision ID: 3d493df2673b
Revises: b345f90a4e21
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d493df2673b'
down_revision: Union[str, Sequence[str], None] = 'b345f90a4e21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('products', sa.Column('embedding_source_text', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('products', 'embedding_source_text')
