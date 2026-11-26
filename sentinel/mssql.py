"""SQL Server and Azure SQL Always On Availability Group telemetry parsing."""

from typing import Any, Dict
from .engine import DatabaseEngineType, NodeRole, NodeTelemetry, SyncState


class MSSQLTelemetryParser:
    """Parses SQL Server / Azure SQL Always On Availability Groups and DMVs:

    - sys.dm_hadr_database_replica_states (synchronization state, secondary lag)
    - sys.dm_os_performance_counters (buffer cache hit ratio, active connections)
    - DBCC SQLPERF(LOGSPACE) or sys.dm_db_log_space_usage (log file percent used)
    """

    @staticmethod
    def parse_primary_telemetry(
        node_id: str,
        perf_data: Dict[str, Any],
        engine_type: DatabaseEngineType = DatabaseEngineType.SQL_SERVER,
    ) -> NodeTelemetry:
        """Parse primary SQL Server instance telemetry."""
        is_alive = bool(perf_data.get("is_alive", True))
        max_user_connections = float(perf_data.get("max_user_connections", 32767))
        user_connections = float(perf_data.get("user_connections", 0))
        conn_pct = (user_connections / max_user_connections * 100.0) if max_user_connections > 0 else 0.0

        log_space_used_pct = float(perf_data.get("log_space_used_pct", 0.0))
        cache_hit_ratio = float(perf_data.get("buffer_cache_hit_ratio", 99.0))
        deadlocks = int(perf_data.get("deadlocks_per_minute", 0))

        return NodeTelemetry(
            node_id=node_id,
            engine=engine_type,
            role=NodeRole.PRIMARY,
            is_alive=is_alive,
            sync_state=SyncState.SYNCHRONIZED,
            replication_lag_seconds=0.0,
            connection_utilization_pct=conn_pct,
            transaction_log_used_pct=log_space_used_pct,
            deadlocks_last_interval=deadlocks,
            cache_hit_ratio_pct=cache_hit_ratio,
            details={
                "user_connections": user_connections,
                "max_user_connections": max_user_connections,
            },
        )

    @staticmethod
    def parse_replica_telemetry(
        node_id: str,
        hadr_row: Dict[str, Any],
        engine_type: DatabaseEngineType = DatabaseEngineType.SQL_SERVER,
    ) -> NodeTelemetry:
        """Parse SQL Server HADR replica state record."""
        raw_sync_desc = str(hadr_row.get("synchronization_state_desc", "SYNCHRONIZED")).upper()
        if raw_sync_desc == "SYNCHRONIZED":
            sync_state = SyncState.SYNCHRONIZED
        elif raw_sync_desc == "SYNCHRONIZING":
            sync_state = SyncState.SYNCHRONIZING
        elif raw_sync_desc in ("NOT SYNCHRONIZING", "NOT_SYNCHRONIZING"):
            sync_state = SyncState.NOT_SYNCHRONIZING
        else:
            sync_state = SyncState.ASYNCHRONOUS

        is_connected = str(hadr_row.get("connected_state_desc", "CONNECTED")).upper() == "CONNECTED"
        is_alive = bool(hadr_row.get("is_alive", is_connected))
        secondary_lag_seconds = float(hadr_row.get("secondary_lag_seconds", 0.0))
        log_pct = float(hadr_row.get("log_space_used_pct", 10.0))

        return NodeTelemetry(
            node_id=node_id,
            engine=engine_type,
            role=NodeRole.REPLICA,
            is_alive=is_alive,
            sync_state=sync_state,
            replication_lag_seconds=secondary_lag_seconds,
            connection_utilization_pct=float(hadr_row.get("connection_utilization_pct", 5.0)),
            transaction_log_used_pct=log_pct,
            deadlocks_last_interval=0,
            cache_hit_ratio_pct=float(hadr_row.get("buffer_cache_hit_ratio", 99.0)),
            details={
                "synchronization_health_desc": hadr_row.get("synchronization_health_desc", "HEALTHY"),
                "availability_group_name": hadr_row.get("availability_group_name", "AG-DEFAULT"),
            },
        )
