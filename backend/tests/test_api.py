"""
API endpoint integration tests using FastAPI TestClient.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "components" in data


def test_liveness():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness():
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_list_projects():
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["name"] == "E-Commerce Checkout API"


def test_list_repositories():
    response = client.get("/api/v1/repositories")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["name"] == "checkout-api"


def test_list_investigations():
    response = client.get("/api/v1/investigations")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1


def test_create_and_get_investigation():
    # Create
    create_payload = {
        "project_id": "demo-project-001",
        "objective": "Test investigation objective: verify automated endpoint handling for regression triage.",
        "mode": "incident",
        "priority": "high",
        "metadata": {"test": True}
    }
    create_res = client.post("/api/v1/investigations", json=create_payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    inv_id = created_data["id"]

    # Get by ID
    get_res = client.get(f"/api/v1/investigations/{inv_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == inv_id


def test_list_approvals():
    response = client.get("/api/v1/approvals")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_findings():
    response = client.get("/api/v1/findings")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
