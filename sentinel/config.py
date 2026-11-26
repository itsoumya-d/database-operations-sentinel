"""Configuration and policy definitions for database failover and health governance."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FailoverPolicy:
    """Thresholds and constraints for evaluating primary health and replica promotion viability."""

    max_replication_lag_seconds: float = 5.0
    max_connection_utilization_pct: float = 85.0
    max_transaction_log_used_pct: float = 90.0
    min_healthy_replicas: int = 1
    max_deadlocks_per_minute: int = 5
    require_strict_quorum: bool = True

    def __post_init__(self) -> None:
        if self.max_replication_lag_seconds < 0:
            raise ValueError("max_replication_lag_seconds cannot be negative")
        if not (0.0 <= self.max_connection_utilization_pct <= 100.0):
            raise ValueError("max_connection_utilization_pct must be between 0.0 and 100.0")
        if not (0.0 <= self.max_transaction_log_used_pct <= 100.0):
            raise ValueError("max_transaction_log_used_pct must be between 0.0 and 100.0")
        if self.min_healthy_replicas < 1:
            raise ValueError("min_healthy_replicas must be at least 1")
        if self.max_deadlocks_per_minute < 0:
            raise ValueError("max_deadlocks_per_minute cannot be negative")
