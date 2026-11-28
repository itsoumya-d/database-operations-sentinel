"""Distributed fencing token and write lease coordinator for database failover governance."""

from dataclasses import dataclass, field
import hashlib
import time
from typing import List, Optional


@dataclass(frozen=True)
class FencingToken:
    """Immutable monotonically increasing fencing token representing an exclusive write lease."""

    token_id: int
    holder_node_id: str
    term: int
    issued_at_epoch: float
    expires_at_epoch: float
    quorum_count: int
    signature: str = field(repr=False)

    def is_expired(self, now_epoch: Optional[float] = None) -> bool:
        """Check if lease duration has elapsed relative to given or current timestamp."""
        current = time.time() if now_epoch is None else now_epoch
        return current >= self.expires_at_epoch


class FencingLeaseCoordinator:
    """Coordinates monotonic lease terms, quorum verification, and fencing tokens to prevent split-brain writes."""

    def __init__(self, cluster_id: str, min_quorum_nodes: int = 1):
        if not cluster_id or not cluster_id.strip():
            raise ValueError("cluster_id cannot be empty or whitespace")
        if min_quorum_nodes < 1:
            raise ValueError("min_quorum_nodes must be at least 1")

        self.cluster_id = cluster_id.strip()
        self.min_quorum_nodes = min_quorum_nodes
        self._current_term: int = 0
        self._token_counter: int = 0
        self._active_token: Optional[FencingToken] = None

    @property
    def current_term(self) -> int:
        return self._current_term

    @property
    def active_token(self) -> Optional[FencingToken]:
        return self._active_token

    def acquire_lease(
        self,
        candidate_node_id: str,
        quorum_nodes: List[str],
        lease_duration_seconds: float = 30.0,
        now_epoch: Optional[float] = None,
    ) -> FencingToken:
        """Issue a new strictly monotonic fencing token to candidate when quorum is satisfied."""
        if not candidate_node_id or not candidate_node_id.strip():
            raise ValueError("candidate_node_id cannot be empty or blank")
        if lease_duration_seconds <= 0:
            raise ValueError("lease_duration_seconds must be positive")

        unique_quorum = {node.strip() for node in quorum_nodes if node and node.strip()}
        if len(unique_quorum) < self.min_quorum_nodes:
            raise RuntimeError(
                f"Quorum threshold not met: required {self.min_quorum_nodes}, got {len(unique_quorum)}"
            )

        current_time = time.time() if now_epoch is None else now_epoch
        self._current_term += 1
        self._token_counter += 1

        signature = self._compute_signature(
            self._token_counter, candidate_node_id.strip(), self._current_term, current_time
        )

        token = FencingToken(
            token_id=self._token_counter,
            holder_node_id=candidate_node_id.strip(),
            term=self._current_term,
            issued_at_epoch=current_time,
            expires_at_epoch=current_time + lease_duration_seconds,
            quorum_count=len(unique_quorum),
            signature=signature,
        )
        self._active_token = token
        return token

    def renew_lease(
        self,
        token: FencingToken,
        quorum_nodes: List[str],
        extension_seconds: float = 30.0,
        now_epoch: Optional[float] = None,
    ) -> FencingToken:
        """Extend the lease for current holder within the active term."""
        if token is None or not self.validate_token(token, now_epoch):
            raise ValueError("Cannot renew an invalid, expired, or non-active fencing token")
        if extension_seconds <= 0:
            raise ValueError("extension_seconds must be positive")

        unique_quorum = {node.strip() for node in quorum_nodes if node and node.strip()}
        if len(unique_quorum) < self.min_quorum_nodes:
            raise RuntimeError(
                f"Quorum threshold not met for lease renewal: required {self.min_quorum_nodes}, got {len(unique_quorum)}"
            )

        current_time = time.time() if now_epoch is None else now_epoch
        renewed_token = FencingToken(
            token_id=token.token_id,
            holder_node_id=token.holder_node_id,
            term=token.term,
            issued_at_epoch=token.issued_at_epoch,
            expires_at_epoch=current_time + extension_seconds,
            quorum_count=len(unique_quorum),
            signature=token.signature,
        )
        self._active_token = renewed_token
        return renewed_token

    def validate_token(self, token: Optional[FencingToken], now_epoch: Optional[float] = None) -> bool:
        """Verify token matches the active lease, term, and has not expired."""
        if token is None or self._active_token is None:
            return False
        if token.token_id != self._active_token.token_id:
            return False
        if token.term != self._active_token.term or token.term != self._current_term:
            return False
        if token.holder_node_id != self._active_token.holder_node_id:
            return False
        if token.is_expired(now_epoch):
            return False
        return True

    def revoke_lease(self, token: FencingToken, reason: str = "orderly_step_down") -> None:
        """Revoke active write lease upon orderly primary demotion."""
        if self._active_token and self._active_token.token_id == token.token_id:
            self._active_token = None

    def _compute_signature(self, token_id: int, holder: str, term: int, issued_epoch: float) -> str:
        payload = f"{self.cluster_id}:{token_id}:{holder}:{term}:{issued_epoch:.4f}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
