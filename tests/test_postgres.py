from sentinel.engine import DatabaseEngineType, NodeRole, SyncState
from sentinel.postgres import PostgresTelemetryParser


def test_postgres_primary_parser():
    activity = {
        "max_connections": 200,
        "active_connections": 50,
        "is_alive": True,
    }
    db_data = {
        "blks_hit": 99500,
        "blks_read": 500,
        "deadlocks": 2,
        "wal_disk_utilization_pct": 34.5,
    }
    telemetry = PostgresTelemetryParser.parse_primary_telemetry("pg-prod-primary-01", activity, db_data)

    assert telemetry.node_id == "pg-prod-primary-01"
    assert telemetry.engine == DatabaseEngineType.POSTGRESQL
    assert telemetry.role == NodeRole.PRIMARY
    assert telemetry.is_alive is True
    assert telemetry.connection_utilization_pct == 25.0
    assert telemetry.cache_hit_ratio_pct == 99.5
    assert telemetry.deadlocks_last_interval == 2
    assert telemetry.transaction_log_used_pct == 34.5


def test_postgres_standby_parser():
    row = {
        "sync_state": "sync",
        "replay_lag_seconds": 0.015,
        "is_connected": True,
        "client_addr": "10.0.1.20",
        "application_name": "pg_standby_sync_01",
        "connection_utilization_pct": 12.0,
        "wal_disk_utilization_pct": 30.0,
    }
    telemetry = PostgresTelemetryParser.parse_standby_telemetry("pg-standby-01", row)

    assert telemetry.node_id == "pg-standby-01"
    assert telemetry.engine == DatabaseEngineType.POSTGRESQL
    assert telemetry.role == NodeRole.STANDBY
    assert telemetry.sync_state == SyncState.SYNCHRONIZED
    assert telemetry.replication_lag_seconds == 0.015
    assert telemetry.is_alive is True
    assert telemetry.is_replica() is True
