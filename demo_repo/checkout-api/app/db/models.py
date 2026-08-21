"""
Database models.
"""
from sqlalchemy import Column, String, Integer, Float, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(String(36), primary_key=True)
    # NOTE: product_id has NO database index — this is the bug.
    # Commit 3a8f2b1 removed the index during a "schema cleanup" task.
    product_id = Column(String(64), nullable=False)  # Missing: index=True
    warehouse_id = Column(String(64), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    reserved = Column(Integer, nullable=False, default=0)

    def to_dict(self):
        return {"id": self.id, "product_id": self.product_id, "quantity": self.quantity}


class Order(Base):
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    total = Column(Float, nullable=False)
