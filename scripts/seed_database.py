"""
Seed the database with an initial demo project, repository, and investigation.
Run: python scripts/seed_database.py
"""
from __future__ import annotations

import asyncio
import sys
import os

# Ensure backend is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.config import settings
from app.db.database import AsyncSessionLocal, create_db_and_tables
from app.db.models import Project, Repository, Investigation
from app.core.security import hash_password


async def seed() -> None:
    print(f"Seeding database: {settings.DATABASE_URL}")
    await create_db_and_tables()

    async with AsyncSessionLocal() as db:
        # Check if already seeded
        from sqlalchemy import select, func
        count = (await db.execute(select(func.count()).select_from(Project))).scalar_one()
        if count > 0:
            print("Database already seeded. Skipping.")
            return

        # -- Demo Project --
        project = Project(
            id="demo-project-001",
            name="E-Commerce Checkout API",
            description="Primary checkout and payment processing service. Handles order creation, inventory reservation, and payment gateway integration.",
            configuration={
                "language": "Python",
                "framework": "FastAPI",
                "primary_service": "checkout-api",
                "alert_thresholds": {"p95_latency_ms": 200, "error_rate_pct": 0.5},
            },
        )
        db.add(project)

        # -- Demo Repository --
        repo = Repository(
            id="demo-repo-001",
            project_id="demo-project-001",
            name="checkout-api",
            url="https://github.com/example-org/checkout-api",
            local_path="./demo_repo/checkout-api",
            branch="main",
            language="Python",
            framework="FastAPI",
            metadata_={"lines_of_code": 8420, "test_coverage": 71.3},
        )
        db.add(repo)

        # -- Demo Investigation (INC-001: Database Regression) --
        investigation = Investigation(
            id="demo-investigation-001",
            project_id="demo-project-001",
            objective=(
                "The checkout API is experiencing p95 latency of 284ms, exceeding our SLA of 200ms. "
                "The regression started approximately 2 hours ago. No infrastructure changes were made. "
                "Investigate the root cause and recommend remediation."
            ),
            mode="incident",
            status="created",
            priority="critical",
            created_by=None,
            langgraph_thread_id="demo-thread-001",
            metadata_={
                "workspace_path": "./demo_repo/checkout-api",
                "service_name": "checkout-api",
                "primary_endpoint": "/api/v1/checkout",
                "severity": "critical",
                "time_window": {
                    "start": "2024-01-15T12:00:00Z",
                    "end": "2024-01-15T14:00:00Z",
                },
            },
        )
        db.add(investigation)

        # -- Audit Investigation --
        audit_inv = Investigation(
            id="demo-investigation-002",
            project_id="demo-project-001",
            objective=(
                "Perform a comprehensive security and code quality audit of the checkout-api repository. "
                "Identify any SQL injection risks, missing input validation, bare exception handlers, "
                "insufficient test coverage, and insecure dependency versions."
            ),
            mode="audit",
            status="created",
            priority="high",
            created_by=None,
            langgraph_thread_id="demo-thread-002",
            metadata_={
                "workspace_path": "./demo_repo/checkout-api",
                "service_name": "checkout-api",
            },
        )
        db.add(audit_inv)

        await db.commit()
        print("[SUCCESS] Database seeded successfully.")
        print(f"   Project ID:  {project.id}")
        print(f"   Repo ID:     {repo.id}")
        print(f"   Incident ID: {investigation.id}")
        print(f"   Audit ID:    {audit_inv.id}")


if __name__ == "__main__":
    asyncio.run(seed())
