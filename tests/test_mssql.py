from sentinel.engine import DatabaseEngineType, NodeRole, SyncState
from sentinel.mssql import MSSQLTelemetryParser


def test_mssql_primary_parser():
    perf = {
        "is_alive": True,
        "max_user_connections": 1000,
        "user_connections": 320,
        "log_space_used_pct": 45.2,
        "buffer_cache_hit_ratio": 99.8,
        "deadlocks_per_minute": 1,
    }
    t = MSSQLTelemetryParser.parse_primary_telemetry("mssql-ag-primary", perf, DatabaseEngineType.SQL_SERVER)

    assert t.node_id == "mssql-ag-primary"
    assert t.engine == DatabaseEngineType.SQL_SERVER
    assert t.role == NodeRole.PRIMARY
    assert t.is_alive is True
    assert t.connection_utilization_pct == 32.0
    assert t.transaction_log_used_pct == 45.2
    assert t.deadlocks_last_interval == 1


def test_mssql_replica_parser():
    hadr = {
        "synchronization_state_desc": "SYNCHRONIZED",
        "connected_state_desc": "CONNECTED",
        "secondary_lag_seconds": 0.05,
        "log_space_used_pct": 20.0,
        "synchronization_health_desc": "HEALTHY",
        "availability_group_name": "AG-PROD-CLUSTER",
    }
    t = MSSQLTelemetryParser.parse_replica_telemetry("mssql-ag-sec-01", hadr, DatabaseEngineType.AZURE_SQL)

    assert t.node_id == "mssql-ag-sec-01"
    assert t.engine == DatabaseEngineType.AZURE_SQL
    assert t.role == NodeRole.REPLICA
    assert t.sync_state == SyncState.SYNCHRONIZED
    assert t.replication_lag_seconds == 0.05
    assert t.is_alive is True
