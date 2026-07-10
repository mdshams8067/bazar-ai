"""switch to supabase auth: profiles table, uuid user ids

Revision ID: 93b519c4bc09
Revises: d0ad8423fdc2
Create Date: 2026-07-10 16:22:39.339103

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '93b519c4bc09'
down_revision: Union[str, Sequence[str], None] = 'd0ad8423fdc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Hand-adjusted from the raw autogenerate output in three ways:
    1. FK constraints referencing `users` are dropped before `users`
       itself, not after — Postgres refuses to drop a table other
       constraints still depend on.
    2. user_id on cart_items/orders is dropped and re-added rather than
       type-altered in place — integer -> UUID has no meaningful implicit
       cast for Postgres to perform. Both tables are empty at this point
       in the chain (this database was created fresh by the two
       migrations immediately before this one), so there's no real data
       to convert anyway.
    3. The unique constraint on cart_items and the index on orders.user_id
       both depend on that column, so they're dropped first and
       explicitly recreated after — dropping a column doesn't reliably
       take a same-named constraint/index with it.
    """
    op.create_table('profiles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('phone', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    op.drop_constraint(op.f('cart_items_user_id_fkey'), 'cart_items', type_='foreignkey')
    op.drop_constraint(op.f('orders_user_id_fkey'), 'orders', type_='foreignkey')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    op.drop_constraint('uq_cart_user_product', 'cart_items', type_='unique')
    op.drop_column('cart_items', 'user_id')
    op.add_column('cart_items', sa.Column('user_id', sa.UUID(), nullable=False))
    op.create_foreign_key(None, 'cart_items', 'profiles', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint('uq_cart_user_product', 'cart_items', ['user_id', 'product_id'])

    op.drop_index(op.f('ix_orders_user_id'), table_name='orders')
    op.drop_column('orders', 'user_id')
    op.add_column('orders', sa.Column('user_id', sa.UUID(), nullable=False))
    op.create_foreign_key(None, 'orders', 'profiles', ['user_id'], ['id'])
    op.create_index(op.f('ix_orders_user_id'), 'orders', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema. Only ever meant to run against the empty database
    this migration itself started from — like upgrade(), it drops/re-adds
    user_id rather than casting, and explicitly recreates the constraint/
    index that depend on it (see upgrade() for why)."""
    op.drop_constraint(None, 'orders', type_='foreignkey')
    op.drop_constraint(None, 'cart_items', type_='foreignkey')

    op.create_table('users',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('email', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('hashed_password', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('phone', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('is_active', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('users_pkey'))
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.drop_index(op.f('ix_orders_user_id'), table_name='orders')
    op.drop_column('orders', 'user_id')
    op.add_column('orders', sa.Column('user_id', sa.INTEGER(), nullable=False))
    op.create_foreign_key(op.f('orders_user_id_fkey'), 'orders', 'users', ['user_id'], ['id'])
    op.create_index(op.f('ix_orders_user_id'), 'orders', ['user_id'], unique=False)

    op.drop_constraint('uq_cart_user_product', 'cart_items', type_='unique')
    op.drop_column('cart_items', 'user_id')
    op.add_column('cart_items', sa.Column('user_id', sa.INTEGER(), nullable=False))
    op.create_foreign_key(op.f('cart_items_user_id_fkey'), 'cart_items', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint('uq_cart_user_product', 'cart_items', ['user_id', 'product_id'])

    op.drop_table('profiles')
