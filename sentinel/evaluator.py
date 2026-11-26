"""Failover policy evaluator and high availability governance logic."""

from datetime import datetime, timezone
from typing import List, Optional

from .config import FailoverPolicy
from .engine import (
    ClusterHealthReport,
    DatabaseEngineType,
    FailoverRecommendation,
    NodeRole,
    NodeTelemetry,
    SyncState,
)


class FailoverEvaluator:
    """Evaluates cluster telemetry against FailoverPolicy to formulate failover recommendations."""

    def __init__(self, policy: Optional[FailoverPolicy] = None) -> None:
        self.policy = policy or FailoverPolicy()

    def evaluate_cluster(
        self,
        cluster_id: str,
        engine: DatabaseEngineType,
        primary: Optional[NodeTelemetry],
        replicas: List[NodeTelemetry],
    ) -> ClusterHealthReport:
        """Run failover policy rules across primary and available standby/replica nodes."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Evaluate Primary Status
        if primary is None or not primary.is_alive:
            return self._handle_primary_down(cluster_id, engine, replicas, now_iso)

        primary_saturated = (
            primary.connection_utilization_pct >= self.policy.max_connection_utilization_pct
            or primary.transaction_log_used_pct >= self.policy.max_transaction_log_used_pct
            or primary.deadlocks_last_interval >= self.policy.max_deadlocks_per_minute
        )

        # Steady State (Primary healthy, not saturated)
        if not primary_saturated:
            return ClusterHealthReport(
                cluster_id=cluster_id,
                engine=engine,
                primary_node_id=primary.node_id,
                is_primary_alive=True,
                is_primary_saturated=False,
                recommendation=FailoverRecommendation.NONE_STEADY_STATE,
                recommended_target_node_id=None,
                candidate_replicas=replicas,
                rationale="Primary database instance is healthy, responsive, and within all operational SLOs.",
                timestamp_iso=now_iso,
            )

        # Primary is saturated/degraded
        reasons = []
        if primary.connection_utilization_pct >= self.policy.max_connection_utilization_pct:
            reasons.append(
                f"Connection saturation at {primary.connection_utilization_pct:.1f}% "
                f"(max {self.policy.max_connection_utilization_pct:.1f}%)"
            )
        if primary.transaction_log_used_pct >= self.policy.max_transaction_log_used_pct:
            reasons.append(
                f"Transaction log utilization at {primary.transaction_log_used_pct:.1f}% "
                f"(max {self.policy.max_transaction_log_used_pct:.1f}%)"
            )
        if primary.deadlocks_last_interval >= self.policy.max_deadlocks_per_minute:
            reasons.append(
                f"Deadlocks per interval at {primary.deadlocks_last_interval} "
                f"(max {self.policy.max_deadlocks_per_minute})"
            )

        return ClusterHealthReport(
            cluster_id=cluster_id,
            engine=engine,
            primary_node_id=primary.node_id,
            is_primary_alive=True,
            is_primary_saturated=True,
            recommendation=FailoverRecommendation.DEGRADED_MANUAL_REVIEW_REQUIRED,
            recommended_target_node_id=None,
            candidate_replicas=replicas,
            rationale="Primary is online but degraded: " + "; ".join(reasons),
            timestamp_iso=now_iso,
        )

    def _handle_primary_down(
        self,
        cluster_id: str,
        engine: DatabaseEngineType,
        replicas: List[NodeTelemetry],
        now_iso: str,
    ) -> ClusterHealthReport:
        """Evaluate replica candidates when primary is unresponsive or crashed."""
        live_replicas = [r for r in replicas if r.is_alive]

        if len(live_replicas) < self.policy.min_healthy_replicas:
            return ClusterHealthReport(
                cluster_id=cluster_id,
                engine=engine,
                primary_node_id=None,
                is_primary_alive=False,
                is_primary_saturated=False,
                recommendation=FailoverRecommendation.BLOCKED_INSUFFICIENT_QUORUM,
                recommended_target_node_id=None,
                candidate_replicas=replicas,
                rationale=(
                    f"Primary is down, but only {len(live_replicas)} live replicas are available "
                    f"(minimum required: {self.policy.min_healthy_replicas}). Failover blocked to avoid split-brain."
                ),
                timestamp_iso=now_iso,
            )

        # Filter candidate replicas that satisfy synchronization and lag SLOs
        viable_candidates = []
        for r in live_replicas:
            is_sync_ok = r.sync_state in (SyncState.SYNCHRONIZED, SyncState.SYNCHRONIZING)
            is_lag_ok = r.replication_lag_seconds <= self.policy.max_replication_lag_seconds
            if is_sync_ok and is_lag_ok:
                viable_candidates.append(r)

        if not viable_candidates:
            # Check why candidates were disqualified
            min_lag = min([r.replication_lag_seconds for r in live_replicas], default=0.0)
            return ClusterHealthReport(
                cluster_id=cluster_id,
                engine=engine,
                primary_node_id=None,
                is_primary_alive=False,
                is_primary_saturated=False,
                recommendation=FailoverRecommendation.BLOCKED_REPLICA_LAG_EXCEEDED,
                recommended_target_node_id=None,
                candidate_replicas=replicas,
                rationale=(
                    f"Primary is down, but all live replicas exceed acceptable replication lag threshold "
                    f"({self.policy.max_replication_lag_seconds}s). Best replica lag: {min_lag:.2f}s. "
                    "Failover blocked to prevent data loss."
                ),
                timestamp_iso=now_iso,
            )

        # Select candidate with lowest lag, then highest cache hit ratio
        best_candidate = min(
            viable_candidates,
            key=lambda r: (r.replication_lag_seconds, -r.cache_hit_ratio_pct),
        )

        return ClusterHealthReport(
            cluster_id=cluster_id,
            engine=engine,
            primary_node_id=None,
            is_primary_alive=False,
            is_primary_saturated=False,
            recommendation=FailoverRecommendation.PROMOTE_REPLICA,
            recommended_target_node_id=best_candidate.node_id,
            candidate_replicas=viable_candidates,
            rationale=(
                f"Primary instance is unreachable. Promoted replica '{best_candidate.node_id}' meets strict quorum "
                f"with minimal replication lag ({best_candidate.replication_lag_seconds:.3f}s)."
            ),
            timestamp_iso=now_iso,
        )
