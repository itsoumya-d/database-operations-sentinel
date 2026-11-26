import json
from sentinel.engine import (
    ClusterHealthReport,
    DatabaseEngineType,
    FailoverRecommendation,
    NodeRole,
    NodeTelemetry,
    SyncState,
)
from sentinel.reporter import format_health_report_json, format_health_report_markdown


def test_reporter_json_and_markdown():
    r1 = NodeTelemetry(
        node_id="rep-01",
        engine=DatabaseEngineType.POSTGRESQL,
        role=NodeRole.STANDBY,
        is_alive=True,
        sync_state=SyncState.SYNCHRONIZED,
        replication_lag_seconds=0.012,
        connection_utilization_pct=15.0,
        transaction_log_used_pct=25.0,
    )
    report = ClusterHealthReport(
        cluster_id="pg-prod-primary",
        engine=DatabaseEngineType.POSTGRESQL,
        primary_node_id="pg-01",
        is_primary_alive=True,
        is_primary_saturated=False,
        recommendation=FailoverRecommendation.NONE_STEADY_STATE,
        recommended_target_node_id=None,
        candidate_replicas=[r1],
        rationale="Primary is healthy.",
        timestamp_iso="2026-11-26T00:00:00Z",
    )

    json_str = format_health_report_json(report)
    parsed = json.loads(json_str)
    assert parsed["cluster_id"] == "pg-prod-primary"
    assert parsed["governance"]["recommendation"] == "NONE_STEADY_STATE"
    assert len(parsed["replicas_evaluated"]) == 1

    md_str = format_health_report_markdown(report)
    assert "# Database Operations Telemetry - Cluster `pg-prod-primary`" in md_str
    assert "NONE_STEADY_STATE" in md_str
    assert "rep-01" in md_str
