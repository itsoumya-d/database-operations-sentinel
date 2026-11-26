"""PostgreSQL telemetry parsing and metric extraction."""

from typing import Any, Dict, List
from .engine import DatabaseEngineType, NodeRole, NodeTelemetry, SyncState


class PostgresTelemetryParser:
    """Parses row dictionaries or raw result records from PostgreSQL DMV-equivalents:

    - pg_stat_replication (standby replication state and lag)
    - pg_stat_database (cache hit ratio, deadlocks, xact counts)
    - pg_stat_activity (connection saturation)
    """

    @staticmethod
    def parse_primary_telemetry(
        node_id: str,
        activity_data: Dict[str, Any],
        database_data: Dict[str, Any],
    ) -> NodeTelemetry:
        """Parse primary PostgreSQL instance telemetry."""
        max_conn = float(activity_data.get("max_connections", 100))
        active_conn = float(activity_data.get("active_connections", 0))
        conn_pct = (active_conn / max_conn * 100.0) if max_conn > 0 else 0.0

        blks_hit = float(database_data.get("blks_hit", 0))
        blks_read = float(database_data.get("blks_read", 0))
        total_blocks = blks_hit + blks_read
        cache_hit_ratio = (blks_hit / total_blocks * 100.0) if total_blocks > 0 else 100.0

        deadlocks = int(database_data.get("deadlocks", 0))
        is_alive = bool(activity_data.get("is_alive", True))

        # In PG, WAL archive utilization or disk percent can be supplied
        wal_pct = float(database_data.get("wal_disk_utilization_pct", 0.0))

        return NodeTelemetry(
            node_id=node_id,
            engine=DatabaseEngineType.POSTGRESQL,
            role=NodeRole.PRIMARY,
            is_alive=is_alive,
            sync_state=SyncState.SYNCHRONIZED,
            replication_lag_seconds=0.0,
            connection_utilization_pct=conn_pct,
            transaction_log_used_pct=wal_pct,
            deadlocks_last_interval=deadlocks,
            cache_hit_ratio_pct=cache_hit_ratio,
            details={"active_connections": active_conn, "max_connections": max_conn},
        )

    @staticmethod
    def parse_standby_telemetry(
        node_id: str,
        stat_replication_row: Dict[str, Any],
    ) -> NodeTelemetry:
        """Parse PostgreSQL pg_stat_replication row for a connected standby."""
        sync_state_str = str(stat_replication_row.get("sync_state", "async")).lower()
        sync_state = (
            SyncState.SYNCHRONIZED
            if sync_state_str == "sync"
            else SyncState.ASYNCHRONOUS
        )

        lag_sec = float(stat_replication_row.get("replay_lag_seconds", 0.0))
        is_alive = bool(stat_replication_row.get("is_connected", True))

        return NodeTelemetry(
            node_id=node_id,
            engine=DatabaseEngineType.POSTGRESQL,
            role=NodeRole.STANDBY,
            is_alive=is_alive,
            sync_state=sync_state,
            replication_lag_seconds=lag_sec,
            connection_utilization_pct=float(stat_replication_row.get("connection_utilization_pct", 10.0)),
            transaction_log_used_pct=float(stat_replication_row.get("wal_disk_utilization_pct", 15.0)),
            deadlocks_last_interval=0,
            cache_hit_ratio_pct=float(stat_replication_row.get("cache_hit_ratio_pct", 99.5)),
            details={
                "client_addr": stat_replication_row.get("client_addr"),
                "application_name": stat_replication_row.get("application_name"),
            },
        )
