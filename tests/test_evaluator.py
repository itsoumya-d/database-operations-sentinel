from sentinel.config import FailoverPolicy
from sentinel.engine import (
    DatabaseEngineType,
    FailoverRecommendation,
    NodeRole,
    NodeTelemetry,
    SyncState,
)
from sentinel.evaluator import FailoverEvaluator


def test_evaluator_steady_state():
    evaluator = FailoverEvaluator()
    primary = NodeTelemetry(
        node_id="p-01",
        engine=DatabaseEngineType.POSTGRESQL,
        role=NodeRole.PRIMARY,
        is_alive=True,
        connection_utilization_pct=40.0,
        transaction_log_used_pct=30.0,
        deadlocks_last_interval=0,
    )
    replica = NodeTelemetry(
        node_id="r-01",
        engine=DatabaseEngineType.POSTGRESQL,
        role=NodeRole.STANDBY,
        is_alive=True,
        sync_state=SyncState.SYNCHRONIZED,
        replication_lag_seconds=0.01,
    )

    report = evaluator.evaluate_cluster("pg-cluster-01", DatabaseEngineType.POSTGRESQL, primary, [replica])
    assert report.recommendation == FailoverRecommendation.NONE_STEADY_STATE
    assert report.is_primary_alive is True
    assert report.is_primary_saturated is False
    assert report.recommended_target_node_id is None


def test_evaluator_primary_saturated():
    evaluator = FailoverEvaluator(FailoverPolicy(max_connection_utilization_pct=80.0))
    primary = NodeTelemetry(
        node_id="p-01",
        engine=DatabaseEngineType.POSTGRESQL,
        role=NodeRole.PRIMARY,
        is_alive=True,
        connection_utilization_pct=92.0,
    )
    report = evaluator.evaluate_cluster("pg-cluster-01", DatabaseEngineType.POSTGRESQL, primary, [])
    assert report.recommendation == FailoverRecommendation.DEGRADED_MANUAL_REVIEW_REQUIRED
    assert report.is_primary_saturated is True
    assert "Connection saturation" in report.rationale


def test_evaluator_primary_down_safe_promotion():
    evaluator = FailoverEvaluator(FailoverPolicy(max_replication_lag_seconds=3.0, min_healthy_replicas=1))
    rep1 = NodeTelemetry(
        node_id="r-01",
        engine=DatabaseEngineType.SQL_SERVER,
        role=NodeRole.REPLICA,
        is_alive=True,
        sync_state=SyncState.SYNCHRONIZED,
        replication_lag_seconds=0.25,
        cache_hit_ratio_pct=99.0,
    )
    rep2 = NodeTelemetry(
        node_id="r-02",
        engine=DatabaseEngineType.SQL_SERVER,
        role=NodeRole.REPLICA,
        is_alive=True,
        sync_state=SyncState.SYNCHRONIZED,
        replication_lag_seconds=1.20,
        cache_hit_ratio_pct=98.5,
    )

    report = evaluator.evaluate_cluster("mssql-cluster-01", DatabaseEngineType.SQL_SERVER, None, [rep1, rep2])
    assert report.recommendation == FailoverRecommendation.PROMOTE_REPLICA
    assert report.recommended_target_node_id == "r-01"
    assert "Promoted replica 'r-01'" in report.rationale


def test_evaluator_primary_down_blocked_lag():
    evaluator = FailoverEvaluator(FailoverPolicy(max_replication_lag_seconds=2.0))
    rep = NodeTelemetry(
        node_id="r-01",
        engine=DatabaseEngineType.POSTGRESQL,
        role=NodeRole.STANDBY,
        is_alive=True,
        sync_state=SyncState.SYNCHRONIZED,
        replication_lag_seconds=15.0,  # exceeds SLA
    )
    report = evaluator.evaluate_cluster("pg-cluster-01", DatabaseEngineType.POSTGRESQL, None, [rep])
    assert report.recommendation == FailoverRecommendation.BLOCKED_REPLICA_LAG_EXCEEDED
    assert report.recommended_target_node_id is None
    assert "exceed acceptable replication lag" in report.rationale


def test_evaluator_primary_down_insufficient_quorum():
    evaluator = FailoverEvaluator(FailoverPolicy(min_healthy_replicas=2))
    rep = NodeTelemetry(
        node_id="r-01",
        engine=DatabaseEngineType.POSTGRESQL,
        role=NodeRole.STANDBY,
        is_alive=True,
        sync_state=SyncState.SYNCHRONIZED,
        replication_lag_seconds=0.01,
    )
    report = evaluator.evaluate_cluster("pg-cluster-01", DatabaseEngineType.POSTGRESQL, None, [rep])
    assert report.recommendation == FailoverRecommendation.BLOCKED_INSUFFICIENT_QUORUM
    assert "only 1 live replicas are available" in report.rationale
