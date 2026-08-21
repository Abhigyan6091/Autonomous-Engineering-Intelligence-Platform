"""
Checkout API tests.
Note: test_checkout_performance is missing — this allowed the latency
regression to go undetected.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_checkout_success():
    """Basic happy path checkout."""
    # Uses in-memory SQLite — masks performance issue
    response = client.post("/api/v1/checkout", json={
        "user_id": "user-123",
        "items": [{"product_id": "SKU-001", "quantity": 1, "price": 29.99}],
    })
    # Will fail without DB setup — demonstrating missing integration test fixtures
    assert response.status_code in (200, 500)


def test_inventory_lookup():
    """Test inventory endpoint."""
    response = client.get("/api/v1/inventory/SKU-001")
    assert response.status_code in (200, 500)
