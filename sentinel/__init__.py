"""Database Operations Sentinel.

Multi-engine database telemetry, replication lag monitoring, and automated
failover policy governance for PostgreSQL and SQL Server / Azure SQL.
"""

from .config import FailoverPolicy
from .engine import (
    DatabaseEngineType,
    NodeRole,
    SyncState,
    FailoverRecommendation,
    NodeTelemetry,
    ClusterHealthReport,
)
from .postgres import PostgresTelemetryParser
from .mssql import MSSQLTelemetryParser
from .evaluator import FailoverEvaluator
from .reporter import format_health_report_json, format_health_report_markdown

__version__ = "0.1.0"
__all__ = [
    "FailoverPolicy",
    "DatabaseEngineType",
    "NodeRole",
    "SyncState",
    "FailoverRecommendation",
    "NodeTelemetry",
    "ClusterHealthReport",
    "PostgresTelemetryParser",
    "MSSQLTelemetryParser",
    "FailoverEvaluator",
    "format_health_report_json",
    "format_health_report_markdown",
]
