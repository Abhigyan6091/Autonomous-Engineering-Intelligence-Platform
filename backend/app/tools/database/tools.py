"""
Safe read-only database exploration tools.
Only SELECT and EXPLAIN operations are permitted. No DDL/DML write actions.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from app.tools.base import BaseTool


class ReadSchemaInput(BaseModel):
    table_name: str | None = Field(None, description="Optional specific table name")


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool


class TableSchema(BaseModel):
    table_name: str
    columns: list[ColumnInfo]
    indexes: list[str]


class ReadSchemaOutput(BaseModel):
    tables: list[TableSchema]


class ReadSchemaTool(BaseTool[ReadSchemaInput, ReadSchemaOutput]):
    name = "read_schema"
    description = "Read database table schemas, columns, foreign keys, and indexes."
    category = "database"
    risk_level = "low"
    required_permissions = ["read:database"]
    input_schema = ReadSchemaInput
    output_schema = ReadSchemaOutput

    async def execute(self, params: ReadSchemaInput, context: dict[str, Any] | None = None) -> ReadSchemaOutput:
        # Returns table schemas with index descriptions
        return ReadSchemaOutput(
            tables=[
                TableSchema(
                    table_name="inventory_items",
                    columns=[
                        ColumnInfo(name="id", data_type="uuid", nullable=False, is_primary_key=True),
                        ColumnInfo(name="product_id", data_type="varchar(64)", nullable=False, is_primary_key=False),
                        ColumnInfo(name="quantity", data_type="integer", nullable=False, is_primary_key=False),
                        ColumnInfo(name="warehouse_id", data_type="varchar(64)", nullable=False, is_primary_key=False),
                    ],
                    indexes=["PRIMARY KEY (id)"],  # Notice product_id is missing an index!
                ),
                TableSchema(
                    table_name="orders",
                    columns=[
                        ColumnInfo(name="id", data_type="uuid", nullable=False, is_primary_key=True),
                        ColumnInfo(name="user_id", data_type="varchar(64)", nullable=False, is_primary_key=False),
                        ColumnInfo(name="status", data_type="varchar(32)", nullable=False, is_primary_key=False),
                    ],
                    indexes=["PRIMARY KEY (id)", "idx_orders_user_id (user_id)"],
                ),
            ]
        )


class ExecuteReadonlyQueryInput(BaseModel):
    query: str = Field(..., description="Read-only SQL query (SELECT / EXPLAIN only)")


class ExecuteReadonlyQueryOutput(BaseModel):
    query: str
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float
    error: str | None = None


class ExecuteReadonlyQueryTool(BaseTool[ExecuteReadonlyQueryInput, ExecuteReadonlyQueryOutput]):
    name = "execute_readonly_query"
    description = "Execute a strictly read-only SQL query or EXPLAIN plan."
    category = "database"
    risk_level = "medium"
    required_permissions = ["read:database"]
    input_schema = ExecuteReadonlyQueryInput
    output_schema = ExecuteReadonlyQueryOutput

    async def execute(self, params: ExecuteReadonlyQueryInput, context: dict[str, Any] | None = None) -> ExecuteReadonlyQueryOutput:
        cleaned = params.query.strip().upper()
        # Security Guardrail: Reject non-SELECT/EXPLAIN queries
        if not (cleaned.startswith("SELECT") or cleaned.startswith("EXPLAIN") or cleaned.startswith("WITH")):
            return ExecuteReadonlyQueryOutput(
                query=params.query,
                rows=[],
                row_count=0,
                execution_time_ms=0,
                error="Security Violation: Only SELECT / EXPLAIN read-only queries are permitted.",
            )

        if "INVENTORY_ITEMS" in cleaned:
            return ExecuteReadonlyQueryOutput(
                query=params.query,
                rows=[{"QUERY PLAN": "Seq Scan on inventory_items  (cost=0.00..1845.20 rows=45000 width=128)"}],
                row_count=1,
                execution_time_ms=145.2,
                error=None,
            )

        return ExecuteReadonlyQueryOutput(
            query=params.query,
            rows=[{"status": "ok"}],
            row_count=1,
            execution_time_ms=1.2,
            error=None,
        )
