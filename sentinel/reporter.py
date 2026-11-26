"""Report serialization and diagnostics output for database operations."""

import json
from .engine import ClusterHealthReport


def format_health_report_json(report: ClusterHealthReport, indent: int = 2) -> str:
    """Serialize health report to clean JSON string."""
    data = {
        "cluster_id": report.cluster_id,
        "engine": report.engine.value,
        "timestamp_iso": report.timestamp_iso,
        "primary": {
            "node_id": report.primary_node_id,
            "is_alive": report.is_primary_alive,
            "is_saturated": report.is_primary_saturated,
        },
        "governance": {
            "recommendation": report.recommendation.value,
            "recommended_target_node_id": report.recommended_target_node_id,
            "rationale": report.rationale,
        },
        "replicas_evaluated": [
            {
                "node_id": r.node_id,
                "role": r.role.value,
                "is_alive": r.is_alive,
                "sync_state": r.sync_state.value,
                "replication_lag_seconds": r.replication_lag_seconds,
                "connection_utilization_pct": r.connection_utilization_pct,
                "transaction_log_used_pct": r.transaction_log_used_pct,
            }
            for r in report.candidate_replicas
        ],
    }
    return json.dumps(data, indent=indent)


def format_health_report_markdown(report: ClusterHealthReport) -> str:
    """Format human-readable markdown status briefing."""
    md = [
        f"# Database Operations Telemetry - Cluster `{report.cluster_id}`",
        f"- **Engine**: `{report.engine.value}`",
        f"- **Timestamp**: `{report.timestamp_iso}`",
        f"- **Primary**: `{'ONLINE' if report.is_primary_alive else 'OFFLINE'}` (`{report.primary_node_id or 'None'}`)",
        f"- **Recommendation**: **`{report.recommendation.value}`**",
    ]
    if report.recommended_target_node_id:
        md.append(f"- **Promotion Target**: `{report.recommended_target_node_id}`")
    md.extend(["", "### Governance Rationale", report.rationale, "", "### Replicas Evaluated"])
    for r in report.candidate_replicas:
        md.append(
            f"- Node `{r.node_id}`: alive={r.is_alive}, sync={r.sync_state.value}, "
            f"lag={r.replication_lag_seconds:.3f}s, conn={r.connection_utilization_pct:.1f}%"
        )
    return "\n".join(md)
