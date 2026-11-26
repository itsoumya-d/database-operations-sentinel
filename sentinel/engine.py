"""Core domain models, enums, and data containers for database operations."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DatabaseEngineType(str, Enum):
    POSTGRESQL = "postgresql"
    SQL_SERVER = "sql_server"
    AZURE_SQL = "azure_sql"


class NodeRole(str, Enum):
    PRIMARY = "primary"
    STANDBY = "standby"
    REPLICA = "replica"
    WITNESS = "witness"


class SyncState(str, Enum):
    SYNCHRONIZED = "synchronized"
    SYNCHRONIZING = "synchronizing"
    ASYNCHRONOUS = "asynchronous"
    NOT_SYNCHRONIZING = "not_synchronizing"
    UNKNOWN = "unknown"


class FailoverRecommendation(str, Enum):
    NONE_STEADY_STATE = "NONE_STEADY_STATE"
    PROMOTE_REPLICA = "PROMOTE_REPLICA"
    DEGRADED_MANUAL_REVIEW_REQUIRED = "DEGRADED_MANUAL_REVIEW_REQUIRED"
    BLOCKED_REPLICA_LAG_EXCEEDED = "BLOCKED_REPLICA_LAG_EXCEEDED"
    BLOCKED_INSUFFICIENT_QUORUM = "BLOCKED_INSUFFICIENT_QUORUM"


@dataclass
class NodeTelemetry:
    """Point-in-time operational metrics for an individual database instance."""

    node_id: str
    engine: DatabaseEngineType
    role: NodeRole
    is_alive: bool = True
    sync_state: SyncState = SyncState.SYNCHRONIZED
    replication_lag_seconds: float = 0.0
    connection_utilization_pct: float = 0.0
    transaction_log_used_pct: float = 0.0
    deadlocks_last_interval: int = 0
    cache_hit_ratio_pct: float = 99.0
    details: dict = field(default_factory=dict)

    def is_replica(self) -> bool:
        return self.role in (NodeRole.STANDBY, NodeRole.REPLICA)


@dataclass
class ClusterHealthReport:
    """Comprehensive evaluation of cluster health and failover recommendation."""

    cluster_id: str
    engine: DatabaseEngineType
    primary_node_id: Optional[str]
    is_primary_alive: bool
    is_primary_saturated: bool
    recommendation: FailoverRecommendation
    recommended_target_node_id: Optional[str]
    candidate_replicas: List[NodeTelemetry]
    rationale: str
    timestamp_iso: str
