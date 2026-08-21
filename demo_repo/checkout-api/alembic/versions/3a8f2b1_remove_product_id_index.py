"""
Remove product_id index from inventory_items (schema cleanup).

Revision ID: 3a8f2b1
Revises: a1b2c3d
Create Date: 2024-01-15 09:32:15.000000

NOTE: This migration was intended to clean up a "duplicate" index but
      accidentally removed the ONLY index on inventory_items.product_id.
      This is the root cause of the latency regression.
"""
from alembic import op

revision = "3a8f2b1"
down_revision = "a1b2c3d"


def upgrade():
    op.drop_index("ix_inventory_items_product_id", table_name="inventory_items")


def downgrade():
    op.create_index("ix_inventory_items_product_id", "inventory_items", ["product_id"])
