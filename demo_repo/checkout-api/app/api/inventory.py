"""
Inventory read endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import InventoryItem

router = APIRouter()


@router.get("/inventory/{product_id}")
def get_inventory(product_id: str, db: Session = Depends(get_db)):
    # BUG: No index on product_id — causes sequential scan across 45k rows.
    # This was fine at 1000 rows but causes p95 latency to jump at scale.
    items = db.query(InventoryItem).filter(
        InventoryItem.product_id == product_id
    ).all()
    return {"product_id": product_id, "items": [i.to_dict() for i in items]}
