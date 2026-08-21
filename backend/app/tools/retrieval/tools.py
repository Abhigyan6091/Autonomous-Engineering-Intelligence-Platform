"""
Documentation, Runbook, and Architectural Knowledge Retrieval Tools.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from app.tools.base import BaseTool


class SearchDocumentationInput(BaseModel):
    query: str = Field(..., description="Query for architecture docs, runbooks, or API specs")
    collection: str = Field("runbooks", description="Collection to search (runbooks | architecture | incidents)")
    max_results: int = Field(3, description="Max documents to return")


class RetrievedDoc(BaseModel):
    title: str
    content: str
    source_uri: str
    relevance_score: float


class SearchDocumentationOutput(BaseModel):
    documents: list[RetrievedDoc]
    total_found: int


class SearchDocumentationTool(BaseTool[SearchDocumentationInput, SearchDocumentationOutput]):
    name = "search_documentation"
    description = "Search repository documentation, architecture guides, and operational runbooks."
    category = "retrieval"
    risk_level = "low"
    required_permissions = ["read:docs"]
    input_schema = SearchDocumentationInput
    output_schema = SearchDocumentationOutput

    async def execute(self, params: SearchDocumentationInput, context: dict[str, Any] | None = None) -> SearchDocumentationOutput:
        # Returns documented runbook guidance
        return SearchDocumentationOutput(
            documents=[
                RetrievedDoc(
                    title="Checkout API Performance Runbook",
                    content=(
                        "Runbook: Checkout API p95 latency budget is 200ms. "
                        "When p95 latency exceeds 250ms, inspect recent commits touching inventory validation "
                        "and verify database indexes on `inventory_items.product_id`."
                    ),
                    source_uri="docs/runbooks/checkout_latency.md",
                    relevance_score=0.94,
                )
            ],
            total_found=1,
        )
