"""
Observability and metrics query tools (Latency, Error Rate, Throughput, Resource Usage).
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from app.tools.base import BaseTool


class QueryLatencyInput(BaseModel):
    endpoint: str = Field(..., description="Target API endpoint or service name (e.g. /api/v1/checkout)")
    time_window_minutes: int = Field(60, description="Time window for metrics aggregation in minutes")


class LatencyDataPoint(BaseModel):
    timestamp: str
    p50_ms: float
    p95_ms: float
    p99_ms: float


class QueryLatencyOutput(BaseModel):
    endpoint: str
    baseline_p95_ms: float
    current_p95_ms: float
    change_pct: float
    datapoints: list[LatencyDataPoint]
    summary: str


class QueryLatencyTool(BaseTool[QueryLatencyInput, QueryLatencyOutput]):
    name = "query_latency"
    description = "Query p50, p95, p99 latency distributions and baseline comparisons for API endpoints."
    category = "metrics"
    risk_level = "low"
    required_permissions = ["read:metrics"]
    input_schema = QueryLatencyInput
    output_schema = QueryLatencyOutput

    async def execute(self, params: QueryLatencyInput, context: dict[str, Any] | None = None) -> QueryLatencyOutput:
        # In synthetic / benchmark runs or live Prometheus integrations:
        baseline_p95 = 210.0
        current_p95 = 284.5
        change = ((current_p95 - baseline_p95) / baseline_p95) * 100.0

        return QueryLatencyOutput(
            endpoint=params.endpoint,
            baseline_p95_ms=baseline_p95,
            current_p95_ms=current_p95,
            change_pct=round(change, 1),
            datapoints=[
                LatencyDataPoint(timestamp="2024-01-15T12:00:00Z", p50_ms=45.0, p95_ms=210.0, p99_ms=310.0),
                LatencyDataPoint(timestamp="2024-01-15T13:00:00Z", p50_ms=85.0, p95_ms=284.5, p99_ms=490.0),
            ],
            summary=f"Endpoint {params.endpoint} experienced a +{round(change, 1)}% increase in p95 latency (210ms -> 284.5ms) after recent deployment.",
        )


class QueryErrorRateInput(BaseModel):
    service: str = Field(..., description="Service or API name")


class QueryErrorRateOutput(BaseModel):
    service: str
    error_rate_pct: float
    baseline_error_rate_pct: float
    top_status_codes: dict[str, int]


class QueryErrorRateTool(BaseTool[QueryErrorRateInput, QueryErrorRateOutput]):
    name = "query_error_rate"
    description = "Query HTTP error rates (4xx, 5xx) and failure distributions."
    category = "metrics"
    risk_level = "low"
    required_permissions = ["read:metrics"]
    input_schema = QueryErrorRateInput
    output_schema = QueryErrorRateOutput

    async def execute(self, params: QueryErrorRateInput, context: dict[str, Any] | None = None) -> QueryErrorRateOutput:
        return QueryErrorRateOutput(
            service=params.service,
            error_rate_pct=3.2,
            baseline_error_rate_pct=0.1,
            top_status_codes={"500": 142, "504": 28, "400": 12},
        )
