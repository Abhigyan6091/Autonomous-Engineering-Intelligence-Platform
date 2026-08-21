"""
Checkout request/response schemas.
"""
from pydantic import BaseModel
from typing import List


class CartItem(BaseModel):
    product_id: str
    quantity: int
    price: float


class CheckoutRequest(BaseModel):
    user_id: str
    items: List[CartItem]


class CheckoutResponse(BaseModel):
    order_id: str
    status: str
