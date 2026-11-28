"""Tests for FencingToken and FencingLeaseCoordinator."""

import pytest
from sentinel.fencing import FencingLeaseCoordinator, FencingToken


def test_normal_lease_acquisition_and_validation():
    coordinator = FencingLeaseCoordinator(cluster_id="pg-prod", min_quorum_nodes=2)
    token = coordinator.acquire_lease(
        candidate_node_id="pg-node-1",
        quorum_nodes=["witness-1", "replica-2"],
        lease_duration_seconds=30.0,
        now_epoch=1000.0,
    )

    assert token.token_id == 1
    assert token.term == 1
    assert token.holder_node_id == "pg-node-1"
    assert token.expires_at_epoch == 1030.0
    assert coordinator.validate_token(token, now_epoch=1010.0) is True


def test_empty_or_invalid_inputs():
    with pytest.raises(ValueError, match="cluster_id cannot be empty"):
        FencingLeaseCoordinator(cluster_id="   ")

    with pytest.raises(ValueError, match="min_quorum_nodes must be at least 1"):
        FencingLeaseCoordinator(cluster_id="pg-prod", min_quorum_nodes=0)

    coordinator = FencingLeaseCoordinator(cluster_id="pg-prod")
    with pytest.raises(ValueError, match="candidate_node_id cannot be empty"):
        coordinator.acquire_lease(candidate_node_id="", quorum_nodes=["w1"])

    with pytest.raises(ValueError, match="lease_duration_seconds must be positive"):
        coordinator.acquire_lease(candidate_node_id="node1", quorum_nodes=["w1"], lease_duration_seconds=-5.0)


def test_stale_token_rejection():
    coordinator = FencingLeaseCoordinator(cluster_id="pg-prod", min_quorum_nodes=1)
    token = coordinator.acquire_lease("node-1", ["witness-1"], lease_duration_seconds=10.0, now_epoch=1000.0)

    # Valid within lease window
    assert coordinator.validate_token(token, now_epoch=1005.0) is True

    # Expired past lease window
    assert coordinator.validate_token(token, now_epoch=1010.0) is False
    assert coordinator.validate_token(token, now_epoch=1015.0) is False
    assert coordinator.validate_token(None) is False


def test_zero_duration_boundary():
    coordinator = FencingLeaseCoordinator(cluster_id="pg-prod", min_quorum_nodes=1)
    with pytest.raises(ValueError, match="lease_duration_seconds must be positive"):
        coordinator.acquire_lease("node-1", ["witness-1"], lease_duration_seconds=0.0)


def test_insufficient_quorum_failure():
    coordinator = FencingLeaseCoordinator(cluster_id="pg-prod", min_quorum_nodes=3)
    with pytest.raises(RuntimeError, match="Quorum threshold not met"):
        coordinator.acquire_lease("node-1", quorum_nodes=["witness-1", "witness-2"])


def test_monotonic_token_invariance():
    coordinator = FencingLeaseCoordinator(cluster_id="pg-prod", min_quorum_nodes=1)
    token1 = coordinator.acquire_lease("node-1", ["w1"], now_epoch=1000.0)
    token2 = coordinator.acquire_lease("node-2", ["w1"], now_epoch=1005.0)
    token3 = coordinator.acquire_lease("node-1", ["w1"], now_epoch=1010.0)

    assert token1.token_id < token2.token_id < token3.token_id
    assert token1.term < token2.term < token3.term
    assert coordinator.validate_token(token1, now_epoch=1010.0) is False
    assert coordinator.validate_token(token2, now_epoch=1010.0) is False
    assert coordinator.validate_token(token3, now_epoch=1010.0) is True


def test_lease_preemption_and_renewal():
    coordinator = FencingLeaseCoordinator(cluster_id="pg-prod", min_quorum_nodes=1)
    token1 = coordinator.acquire_lease("node-1", ["w1"], lease_duration_seconds=20.0, now_epoch=1000.0)

    # Renew token
    renewed = coordinator.renew_lease(token1, ["w1"], extension_seconds=40.0, now_epoch=1010.0)
    assert renewed.expires_at_epoch == 1050.0
    assert coordinator.validate_token(renewed, now_epoch=1020.0) is True

    # Preemption by failover promotion
    token2 = coordinator.acquire_lease("node-2", ["w1"], lease_duration_seconds=20.0, now_epoch=1025.0)
    assert coordinator.validate_token(token2, now_epoch=1026.0) is True
    assert coordinator.validate_token(renewed, now_epoch=1026.0) is False

    # Revocation
    coordinator.revoke_lease(token2)
    assert coordinator.validate_token(token2, now_epoch=1027.0) is False
