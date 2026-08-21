"""
OpenTelemetry observability setup.
Instruments FastAPI, SQLAlchemy, and Redis for distributed tracing.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def setup_observability() -> None:
    """Initialize OpenTelemetry tracing and Prometheus metrics."""
    from app.core.config import settings

    if not settings.OTEL_ENABLED:
        logger.info("OpenTelemetry disabled")
        return

    try:
        _setup_tracing(settings)
        logger.info(
            "OpenTelemetry tracing configured",
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            service=settings.OTEL_SERVICE_NAME,
        )
    except Exception as exc:
        # Observability failure should not block startup
        logger.warning(
            "OpenTelemetry setup failed — tracing disabled",
            error=str(exc),
        )

    if settings.METRICS_ENABLED:
        try:
            _setup_metrics()
            logger.info("Prometheus metrics configured")
        except Exception as exc:
            logger.warning("Metrics setup failed", error=str(exc))


def _setup_tracing(settings: object) -> None:
    """Configure OpenTelemetry OTLP exporter and instrumentations."""
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource(
        attributes={
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.version": "0.1.0",
            "deployment.environment": settings.APP_ENV,
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI
    FastAPIInstrumentor().instrument()

    # Auto-instrument SQLAlchemy (will be applied when engine is created)
    SQLAlchemyInstrumentor().instrument()


def _setup_metrics() -> None:
    """Configure Prometheus metrics via prometheus-fastapi-instrumentator."""
    # Metrics are configured in main.py after the app is created
    # This function sets up custom metrics registry
    from prometheus_client import Counter, Gauge, Histogram

    # We expose these as module-level for import by other modules
    global investigation_duration
    global agent_latency
    global tool_latency
    global llm_latency
    global tool_failures_total
    global agent_retries_total
    global llm_tokens_total
    global investigations_completed_total
    global findings_total
    global approvals_pending
    global estimated_cost_usd_total

    investigation_duration = Histogram(
        "aeip_investigation_duration_seconds",
        "Total investigation duration in seconds",
        labelnames=["mode", "status"],
        buckets=[30, 60, 120, 300, 600, 1800, 3600],
    )

    agent_latency = Histogram(
        "aeip_agent_latency_seconds",
        "Agent execution latency in seconds",
        labelnames=["agent_type"],
        buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0],
    )

    tool_latency = Histogram(
        "aeip_tool_latency_seconds",
        "Tool execution latency in seconds",
        labelnames=["tool_name", "status"],
        buckets=[0.01, 0.1, 0.5, 1.0, 5.0, 30.0],
    )

    llm_latency = Histogram(
        "aeip_llm_latency_seconds",
        "LLM call latency in seconds",
        labelnames=["provider", "model"],
        buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
    )

    tool_failures_total = Counter(
        "aeip_tool_failures_total",
        "Total tool execution failures",
        labelnames=["tool_name", "error_type"],
    )

    agent_retries_total = Counter(
        "aeip_agent_retries_total",
        "Total agent retry attempts",
        labelnames=["agent_type"],
    )

    llm_tokens_total = Counter(
        "aeip_llm_tokens_total",
        "Total LLM tokens used",
        labelnames=["provider", "model", "direction"],  # direction: input|output
    )

    investigations_completed_total = Counter(
        "aeip_investigations_completed_total",
        "Total completed investigations",
        labelnames=["mode", "status"],
    )

    findings_total = Counter(
        "aeip_findings_total",
        "Total findings generated",
        labelnames=["severity"],
    )

    approvals_pending = Gauge(
        "aeip_approvals_pending",
        "Number of investigations waiting for human approval",
    )

    estimated_cost_usd_total = Counter(
        "aeip_estimated_cost_usd_total",
        "Estimated total LLM cost in USD",
        labelnames=["provider", "model"],
    )


def shutdown_observability() -> None:
    """Gracefully shut down OpenTelemetry providers."""
    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except Exception:
        pass


def get_tracer(name: str):  # noqa: ANN201
    """Return an OpenTelemetry tracer for the given module."""
    from opentelemetry import trace
    return trace.get_tracer(name)


# Lazy metric accessors (return None if metrics not initialized)
investigation_duration = None
agent_latency = None
tool_latency = None
llm_latency = None
tool_failures_total = None
agent_retries_total = None
llm_tokens_total = None
investigations_completed_total = None
findings_total = None
approvals_pending = None
estimated_cost_usd_total = None
