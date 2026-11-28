# database-operations-sentinel

[![CI](https://github.com/itsoumya-d/database-operations-sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/itsoumya-d/database-operations-sentinel/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

High-availability database operations, replication lag telemetry, connection pool governance, and automated failover policy engine for PostgreSQL and SQL Server / Azure SQL.

## Overview

In mission-critical transactional platforms running PostgreSQL and SQL Server (including Always On Availability Groups / Azure SQL), maintaining high availability requires strict operational safeguards:
1. **Replication Lag & Data Loss Prevention**: Prohibiting failover to asynchronous or high-latency replicas where data loss (RPO violations) would occur.
2. **Split-Brain Elimination**: Requiring verified replica quorum before permitting automatic promotion.
3. **Saturation & Degradation Detection**: Tracking connection pool exhaustion, transaction log space (`DBCC SQLPERF` / WAL), and deadlock frequency before failover is triggered.

`database-operations-sentinel` provides structured telemetry parsers and deterministic failover governance evaluators across PostgreSQL and SQL Server estates.

## Architecture

```text
       [Database Telemetry DMV Collectors]
           │                         │
  (PostgreSQL pg_stat_*)    (SQL Server HADR / sys.dm_*)
           │                         │
           ▼                         ▼
   [PostgresTelemetryParser] [MSSQLTelemetryParser]
                     │
                     ▼
          [FailoverEvaluator] ◄── [FailoverPolicy (SLOs)]
                     │
      ┌──────────────┴──────────────┐
      ▼                             ▼
[ClusterHealthReport]    [Automated Action]
 - Steady State           - Promote Best Standby
 - Primary Saturated      - Block Promotion (Lag SLA Breach)
 - Primary Unreachable    - Block Promotion (Quorum Lost)
```

## Quick Start

### Installation

```bash
git clone https://github.com/itsoumya-d/database-operations-sentinel.git
cd database-operations-sentinel
python -m pip install -e ".[dev]"
```

### Running Tests

```bash
pytest -v
```

### Example Usage

```python
from sentinel.config import FailoverPolicy
from sentinel.engine import DatabaseEngineType, NodeRole, NodeTelemetry, SyncState
from sentinel.evaluator import FailoverEvaluator
from sentinel.reporter import format_health_report_markdown

# Define operational thresholds
policy = FailoverPolicy(
    max_replication_lag_seconds=2.0,
    max_connection_utilization_pct=85.0,
    min_healthy_replicas=1,
)

evaluator = FailoverEvaluator(policy)

# Simulated primary outage with standby replicas
standby1 = NodeTelemetry(
    node_id="pg-standby-01",
    engine=DatabaseEngineType.POSTGRESQL,
    role=NodeRole.STANDBY,
    is_alive=True,
    sync_state=SyncState.SYNCHRONIZED,
    replication_lag_seconds=0.02,
)

report = evaluator.evaluate_cluster(
    cluster_id="pg-cluster-prod",
    engine=DatabaseEngineType.POSTGRESQL,
    primary=None,  # Primary down
    replicas=[standby1],
)

print(format_health_report_markdown(report))
```

## Features

- **Multi-Engine Telemetry Normalization**: Unified `NodeTelemetry` format across PostgreSQL `pg_stat_replication` and SQL Server `sys.dm_hadr_database_replica_states`.
- **Configurable Governance Policies**: Custom maximum replication lag, connection utilization thresholds, log space limits, and quorum requirements.
- **Failover Safety Circuit-Breakers**: Blocks unsafe promotions if replica lag violates strict recovery point objectives (RPO).
- **Diagnostics Reporting**: Structured JSON and Markdown serialization for integration with PagerDuty, Alertmanager, or SRE dashboards.
- **Fencing Token & Lease Governance**: Monotonic write lease tokens with quorum consensus verification preventing split-brain writes during failover.

## Fencing Token Coordinator

To eliminate split-brain write conflicts when a partitioned primary recovers after failover, `FencingLeaseCoordinator` issues strictly increasing monotonic lease tokens:

- **Monotonic Terms:** Every promotion increments the cluster term and token ID. Older primaries attempting writes with stale tokens are rejected.
- **Quorum Verification:** Lease acquisition and renewals require majority quorum confirmations across witness nodes.
- **Preemption & Revocation:** Orderly step-down revokes leases; failover promotions preempt older holder tokens immediately.

### Example Usage

```python
from sentinel.fencing import FencingLeaseCoordinator

coordinator = FencingLeaseCoordinator(cluster_id="pg-prod", min_quorum_nodes=2)

# New primary candidate acquires lease with quorum confirmation
token = coordinator.acquire_lease(
    candidate_node_id="pg-node-1",
    quorum_nodes=["witness-1", "replica-2"],
    lease_duration_seconds=30.0,
)

# Storage layer validates token before accepting write operations
assert coordinator.validate_token(token) is True
```

### Operational Invariants
- Tokens are immutable and tied to the active term. Lease validation requires both term matching and unexpired epoch duration.

## License

MIT License. Copyright (c) 2026 Soumya Debnath.
