"""
Checkout business logic.
"""
from sqlalchemy.orm import Session
from app.db.models import Order, InventoryItem
from app.schemas.checkout import CheckoutRequest


def process_checkout(db: Session, request: CheckoutRequest) -> dict:
    # N+1 Query: For each item in cart, performs a SEPARATE unindexed lookup
    # on inventory_items by product_id (no index on product_id column).
    for item in request.items:
        inventory = db.query(InventoryItem).filter(
            InventoryItem.product_id == item.product_id  # SEQ SCAN — no index!
        ).first()
        if not inventory or inventory.quantity < item.quantity:
            raise ValueError(f"Insufficient inventory for {item.product_id}")
        inventory.quantity -= item.quantity

    order = Order(
        user_id=request.user_id,
        status="confirmed",
        total=sum(i.price * i.quantity for i in request.items),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"order_id": order.id, "status": "confirmed"}
