import pytest
from sentinel.config import FailoverPolicy


def test_default_policy():
    p = FailoverPolicy()
    assert p.max_replication_lag_seconds == 5.0
    assert p.max_connection_utilization_pct == 85.0
    assert p.max_transaction_log_used_pct == 90.0
    assert p.min_healthy_replicas == 1
    assert p.max_deadlocks_per_minute == 5
    assert p.require_strict_quorum is True


def test_custom_policy():
    p = FailoverPolicy(
        max_replication_lag_seconds=2.5,
        max_connection_utilization_pct=75.0,
        max_transaction_log_used_pct=80.0,
        min_healthy_replicas=2,
    )
    assert p.max_replication_lag_seconds == 2.5
    assert p.min_healthy_replicas == 2


def test_invalid_policy_thresholds():
    with pytest.raises(ValueError, match="max_replication_lag_seconds cannot be negative"):
        FailoverPolicy(max_replication_lag_seconds=-1.0)

    with pytest.raises(ValueError, match="max_connection_utilization_pct must be between 0.0 and 100.0"):
        FailoverPolicy(max_connection_utilization_pct=105.0)

    with pytest.raises(ValueError, match="max_transaction_log_used_pct must be between 0.0 and 100.0"):
        FailoverPolicy(max_transaction_log_used_pct=-5.0)

    with pytest.raises(ValueError, match="min_healthy_replicas must be at least 1"):
        FailoverPolicy(min_healthy_replicas=0)
