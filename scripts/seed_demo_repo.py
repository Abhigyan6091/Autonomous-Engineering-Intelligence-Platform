"""
Creates a synthetic demo repository (INC-001: Database regression) on disk.
This simulates a real Python/FastAPI repository with a latent bug for the agents to discover.

Run: python scripts/seed_demo_repo.py
"""
from __future__ import annotations

import os
import pathlib

BASE = pathlib.Path(__file__).parent.parent / "demo_repo" / "checkout-api"


def write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n")


def init_git_repo() -> None:
    """
    Make the demo repo a real git repository.

    Without its own .git, git tools walk up to the parent repository and
    return that project's history as evidence — and remediation would target
    the wrong repo entirely.
    """
    import subprocess

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(BASE), *args], capture_output=True, text=True
        )

    if (BASE / ".git").exists():
        print("   git repository already initialised")
        return

    git("init", "-q")
    git("config", "user.email", "demo@aeip.local")
    git("config", "user.name", "AEIP Demo Seed")

    # Baseline commit: the code as it was before the regression.
    baseline = BASE / "alembic" / "versions" / "3a8f2b1_remove_product_id_index.py"
    stashed = baseline.read_text() if baseline.exists() else None
    if stashed is not None:
        baseline.unlink()

    git("add", "-A")
    git("commit", "-q", "-m", "baseline: checkout-api before inventory regression")

    # Regression commit: reintroduce the migration that drops the index.
    if stashed is not None:
        baseline.write_text(stashed)
        git("add", "-A")
        git(
            "commit", "-q", "-m",
            "3a8f2b1 perf: drop unused index ix_inventory_items_product_id\n\n"
            "Removes the index on inventory_items.product_id to speed up writes.",
        )

    print("   git repository initialised with baseline + regression commits")


def main() -> None:
    # ── Source files ────────────────────────────────────────────────────────

    write(BASE / "app" / "__init__.py", '"""Checkout API package."""')

    write(BASE / "app" / "main.py", '''"""
Checkout API — main entrypoint.
"""
from fastapi import FastAPI
from app.api import checkout, inventory

app = FastAPI(title="Checkout API", version="1.3.2")
app.include_router(checkout.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
''')

    write(BASE / "app" / "api" / "__init__.py", "")

    write(BASE / "app" / "api" / "checkout.py", '''"""
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
''')

    write(BASE / "app" / "api" / "inventory.py", '''"""
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
''')

    write(BASE / "app" / "services" / "__init__.py", "")

    write(BASE / "app" / "services" / "checkout_service.py", '''"""
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
''')

    write(BASE / "app" / "db" / "__init__.py", "")

    write(BASE / "app" / "db" / "models.py", '''"""
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
''')

    write(BASE / "app" / "db" / "session.py", '''"""
Database session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./checkout.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
''')

    write(BASE / "app" / "schemas" / "__init__.py", "")

    write(BASE / "app" / "schemas" / "checkout.py", '''"""
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
''')

    # ── Migration history (shows the bad commit) ───────────────────────────
    write(BASE / "alembic" / "versions" / "3a8f2b1_remove_product_id_index.py", '''"""
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
''')

    # ── Tests ──────────────────────────────────────────────────────────────
    write(BASE / "tests" / "__init__.py", "")

    write(BASE / "tests" / "test_checkout.py", '''"""
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
''')

    # ── Logs ──────────────────────────────────────────────────────────────
    write(BASE / "logs" / "app.log", '''2024-01-15 11:58:02 INFO  Application started version=1.3.2
2024-01-15 12:00:01 INFO  POST /api/v1/checkout duration_ms=45 status=200
2024-01-15 12:01:15 INFO  POST /api/v1/checkout duration_ms=48 status=200
2024-01-15 12:31:42 INFO  Deployment completed commit=3a8f2b1 version=1.3.3
2024-01-15 12:32:01 INFO  POST /api/v1/checkout duration_ms=187 status=200
2024-01-15 12:33:14 WARNING POST /api/v1/checkout duration_ms=253 status=200 SLOW_REQUEST
2024-01-15 12:34:22 WARNING POST /api/v1/checkout duration_ms=284 status=200 SLOW_REQUEST
2024-01-15 12:35:08 ERROR  POST /api/v1/checkout duration_ms=502 status=500
2024-01-15 12:35:08 ERROR  sqlalchemy.exc.OperationalError: database is locked
2024-01-15 12:36:01 WARNING POST /api/v1/checkout duration_ms=298 status=200 SLOW_REQUEST
2024-01-15 12:37:45 ERROR  POST /api/v1/checkout duration_ms=610 status=500
2024-01-15 12:37:45 ERROR  Traceback (most recent call last):
2024-01-15 12:37:45 ERROR    File "app/services/checkout_service.py", line 12, in process_checkout
2024-01-15 12:37:45 ERROR    inventory = db.query(InventoryItem).filter(InventoryItem.product_id == item.product_id).first()
2024-01-15 12:37:45 ERROR  sqlalchemy.orm.exc.DetachedInstanceError: Instance <InventoryItem at 0x7f3a2b1c4d90> is not bound to a Session
''')

    # ── Docs / Runbooks ────────────────────────────────────────────────────
    write(BASE / "docs" / "runbooks" / "checkout_latency.md", '''# Checkout API Performance Runbook

## Latency Budget

- p50 target: < 50ms
- p95 target: < 200ms (SLA threshold)
- p99 target: < 400ms

## Checkout p95 Regression Checklist

1. **Check recent deployments**: `git log --oneline HEAD~10`
2. **Verify database indexes**: Run `EXPLAIN ANALYZE` on inventory queries
   - Specifically check `ix_inventory_items_product_id` exists
   - `SELECT * FROM pg_indexes WHERE tablename = 'inventory_items';`
3. **Check for N+1 queries**: Review `checkout_service.py` inventory loop
4. **Verify connection pool health**: Check `DB_POOL_SIZE` config (default: 10)
5. **Check third-party payment gateway latency** (Stripe dashboard)

## Known Issues

- **INC-2023-0042**: Removing product_id index causes sequential scan on 45k+ rows.
  Fix: `CREATE INDEX CONCURRENTLY ix_inventory_items_product_id ON inventory_items(product_id);`
''')

    write(BASE / "pyproject.toml", '''[tool.poetry]
name = "checkout-api"
version = "1.3.3"
description = "E-Commerce Checkout API"

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "0.104.1"
sqlalchemy = "2.0.23"
alembic = "1.13.0"
uvicorn = "0.24.0"
pydantic = "2.5.0"
stripe = "7.0.0"

[tool.poetry.dev-dependencies]
pytest = "^7.4"
httpx = "^0.25"
pytest-asyncio = "^0.21"
''')

    write(BASE / "requirements.txt", '''fastapi==0.104.1
sqlalchemy==2.0.23
alembic==1.13.0
uvicorn==0.24.0
pydantic==2.5.0
stripe==7.0.0
''')

    # ── Git history simulation ─────────────────────────────────────────────
    write(BASE / "COMMIT_LOG.txt", '''commit 3a8f2b1 (HEAD -> main)
Author: dev-alice <alice@example.com>
Date:   Mon Jan 15 09:32:15 2024 +0000
    chore: schema cleanup - remove duplicate index

commit a1b2c3d
Author: dev-bob <bob@example.com>
Date:   Fri Jan 12 16:45:01 2024 +0000
    feat: add warehouse_id column to inventory_items

commit 9e8d7c6
Author: dev-alice <alice@example.com>
Date:   Thu Jan 11 11:20:33 2024 +0000
    fix: improve checkout error handling

commit 5f4e3d2
Author: dev-carol <carol@example.com>
Date:   Wed Jan 10 09:15:44 2024 +0000
    feat: add N+1 inventory check loop for multi-item carts
''')

    init_git_repo()

    print("[SUCCESS] Demo repository created at:", BASE)
    print("   Files created:")
    for p in sorted(BASE.rglob("*")):
        if p.is_file():
            print(f"   {p.relative_to(BASE)}")


if __name__ == "__main__":
    main()
