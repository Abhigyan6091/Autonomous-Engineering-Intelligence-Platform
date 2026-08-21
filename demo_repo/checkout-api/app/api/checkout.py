"""
Checkout endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.checkout_service import process_checkout
from app.schemas.checkout import CheckoutRequest, CheckoutResponse

router = APIRouter()


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(request: CheckoutRequest, db: Session = Depends(get_db)):
    try:
        return process_checkout(db, request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
