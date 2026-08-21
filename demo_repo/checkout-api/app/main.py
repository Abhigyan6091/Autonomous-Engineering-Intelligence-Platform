"""
Checkout API — main entrypoint.
"""
from fastapi import FastAPI
from app.api import checkout, inventory

app = FastAPI(title="Checkout API", version="1.3.2")
app.include_router(checkout.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
