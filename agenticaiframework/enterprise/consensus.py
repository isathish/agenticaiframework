"""
Enterprise Consensus Module.

Provides consensus algorithms, voting, and quorum-based
decision making for distributed systems.

Example:
    # Create consensus group
    group = create_consensus_group("cluster", nodes=["n1", "n2", "n3"])
    
    # Propose a value
    result = await group.propose("operation", {"action": "scale", "count": 5})
    
    if result.accepted:
        print(f"Consensus reached: {result.value}")
    
    # With quorum voting
    vote = await quorum.vote("proposal_1", approve=True)
    if await quorum.is_accepted("proposal_1"):
        ...
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ConsensusError(Exception):
    """Consensus error."""
    pass


class NoQuorumError(ConsensusError):
    """No quorum available."""
    pass


class ProposalRejectedError(ConsensusError):
    """Proposal was rejected."""
    pass


class ConsensusState(str, Enum):
    """State of consensus node."""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class VoteType(str, Enum):
    """Type of vote."""
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class ProposalState(str, Enum):
    """State of a proposal."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class QuorumType(str, Enum):
    """Type of quorum calculation."""
    SIMPLE_MAJORITY = "simple_majority"  # > 50%
    TWO_THIRDS = "two_thirds"  # >= 66.67%
    UNANIMOUS = "unanimous"  # 100%
    CUSTOM = "custom"


@dataclass
class Vote:
    """A vote on a proposal."""
    voter_id: str
    proposal_id: str
    vote_type: VoteType
    timestamp: datetime = field(default_factory=datetime.now)
    reason: Optional[str] = None


@dataclass
class Proposal:
    """A consensus proposal."""
    proposal_id: str
    proposer_id: str
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    state: ProposalState = ProposalState.PENDING
    votes: List[Vote] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusResult:
    """Result of consensus operation."""
    accepted: bool
    key: str
    value: Optional[Any] = None
    votes_for: int = 0
    votes_against: int = 0
    total_voters: int = 0
    term: int = 0
    error: Optional[str] = None


@dataclass
class NodeInfo:
    """Information about a consensus node."""
    node_id: str
    address: str
    port: int
    state: ConsensusState = ConsensusState.FOLLOWER
    last_seen: datetime = field(default_factory=datetime.now)
    vote_count: int = 0


@dataclass
class ConsensusConfig:
    """Consensus configuration."""
    quorum_type: QuorumType = QuorumType.SIMPLE_MAJORITY
    custom_quorum_threshold: float = 0.5
    proposal_timeout_seconds: int = 30
    voting_timeout_seconds: int = 10
    election_timeout_ms: int = 5000
    heartbeat_interval_ms: int = 1000


class ProposalStore(ABC):
    """Abstract proposal store."""
    
    @abstractmethod
    async def save_proposal(self, proposal: Proposal) -> None:
        """Save a proposal."""
        pass
    
    @abstractmethod
    async def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """Get a proposal by ID."""
        pass
    
    @abstractmethod
    async def add_vote(self, proposal_id: str, vote: Vote) -> None:
        """Add a vote to a proposal."""
        pass
    
    @abstractmethod
    async def update_state(
        self,
        proposal_id: str,
        state: ProposalState,
    ) -> None:
        """Update proposal state."""
        pass
    
    @abstractmethod
    async def get_pending_proposals(self) -> List[Proposal]:
        """Get all pending proposals."""
        pass


class InMemoryProposalStore(ProposalStore):
    """In-memory proposal store."""
    
    def __init__(self):
        self._proposals: Dict[str, Proposal] = {}
        self._lock = asyncio.Lock()
    
    async def save_proposal(self, proposal: Proposal) -> None:
        async with self._lock:
            self._proposals[proposal.proposal_id] = proposal
    
    async def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        return self._proposals.get(proposal_id)
    
    async def add_vote(self, proposal_id: str, vote: Vote) -> None:
        async with self._lock:
            proposal = self._proposals.get(proposal_id)
            if proposal:
                # Check for duplicate vote
                for v in proposal.votes:
                    if v.voter_id == vote.voter_id:
                        return
                proposal.votes.append(vote)
    
    async def update_state(
        self,
        proposal_id: str,
        state: ProposalState,
    ) -> None:
        async with self._lock:
            proposal = self._proposals.get(proposal_id)
            if proposal:
                proposal.state = state
    
    async def get_pending_proposals(self) -> List[Proposal]:
        return [
            p for p in self._proposals.values()
            if p.state == ProposalState.PENDING
        ]


class QuorumCalculator:
    """Calculate quorum requirements."""
    
    def __init__(
        self,
        quorum_type: QuorumType = QuorumType.SIMPLE_MAJORITY,
        custom_threshold: float = 0.5,
    ):
        self._quorum_type = quorum_type
        self._custom_threshold = custom_threshold
    
    def required_votes(self, total_voters: int) -> int:
        """Calculate required votes for quorum."""
        if self._quorum_type == QuorumType.SIMPLE_MAJORITY:
            return (total_voters // 2) + 1
        
        elif self._quorum_type == QuorumType.TWO_THIRDS:
            return int((total_voters * 2) / 3) + 1
        
        elif self._quorum_type == QuorumType.UNANIMOUS:
            return total_voters
        
        elif self._quorum_type == QuorumType.CUSTOM:
            return int(total_voters * self._custom_threshold) + 1
        
        return (total_voters // 2) + 1
    
    def is_quorum_reached(
        self,
        votes_for: int,
        total_voters: int,
    ) -> bool:
        """Check if quorum is reached."""
        return votes_for >= self.required_votes(total_voters)
    
    def is_rejected(
        self,
        votes_against: int,
        total_voters: int,
    ) -> bool:
        """Check if proposal is definitively rejected."""
        # If enough votes against that quorum can't be reached
        remaining_possible = total_voters - votes_against
        return remaining_possible < self.required_votes(total_voters)


class Quorum:
    """
    Quorum-based voting system.
    """
    
    def __init__(
        self,
        quorum_id: str,
        voters: List[str],
        store: ProposalStore,
        calculator: Optional[QuorumCalculator] = None,
        config: Optional[ConsensusConfig] = None,
    ):
        self._quorum_id = quorum_id
        self._voters = set(voters)
        self._store = store
        self._calculator = calculator or QuorumCalculator()
        self._config = config or ConsensusConfig()
    
    @property
    def quorum_id(self) -> str:
        return self._quorum_id
    
    @property
    def voters(self) -> Set[str]:
        return self._voters.copy()
    
    @property
    def voter_count(self) -> int:
        return len(self._voters)
    
    def add_voter(self, voter_id: str) -> None:
        """Add a voter."""
        self._voters.add(voter_id)
    
    def remove_voter(self, voter_id: str) -> None:
        """Remove a voter."""
        self._voters.discard(voter_id)
    
    async def create_proposal(
        self,
        key: str,
        value: Any,
        proposer_id: str,
        timeout_seconds: Optional[int] = None,
    ) -> Proposal:
        """Create a new proposal."""
        timeout = timeout_seconds or self._config.proposal_timeout_seconds
        
        proposal = Proposal(
            proposal_id=str(uuid.uuid4()),
            proposer_id=proposer_id,
            key=key,
            value=value,
            expires_at=datetime.now() + timedelta(seconds=timeout),
        )
        
        await self._store.save_proposal(proposal)
        
        logger.info(f"Created proposal: {proposal.proposal_id}")
        
        return proposal
    
    async def vote(
        self,
        proposal_id: str,
        voter_id: str,
        approve: bool,
        reason: Optional[str] = None,
    ) -> Vote:
        """Cast a vote on a proposal."""
        if voter_id not in self._voters:
            raise ConsensusError(f"Unknown voter: {voter_id}")
        
        proposal = await self._store.get_proposal(proposal_id)
        if not proposal:
            raise ConsensusError(f"Unknown proposal: {proposal_id}")
        
        if proposal.state != ProposalState.PENDING:
            raise ConsensusError(f"Proposal not pending: {proposal.state}")
        
        vote = Vote(
            voter_id=voter_id,
            proposal_id=proposal_id,
            vote_type=VoteType.APPROVE if approve else VoteType.REJECT,
            reason=reason,
        )
        
        await self._store.add_vote(proposal_id, vote)
        
        # Check if proposal can be resolved
        await self._try_resolve_proposal(proposal_id)
        
        return vote
    
    async def _try_resolve_proposal(self, proposal_id: str) -> None:
        """Try to resolve a proposal based on votes."""
        proposal = await self._store.get_proposal(proposal_id)
        if not proposal or proposal.state != ProposalState.PENDING:
            return
        
        votes_for = sum(
            1 for v in proposal.votes if v.vote_type == VoteType.APPROVE
        )
        votes_against = sum(
            1 for v in proposal.votes if v.vote_type == VoteType.REJECT
        )
        
        if self._calculator.is_quorum_reached(votes_for, len(self._voters)):
            await self._store.update_state(proposal_id, ProposalState.ACCEPTED)
            logger.info(f"Proposal accepted: {proposal_id}")
        
        elif self._calculator.is_rejected(votes_against, len(self._voters)):
            await self._store.update_state(proposal_id, ProposalState.REJECTED)
            logger.info(f"Proposal rejected: {proposal_id}")
    
    async def get_result(self, proposal_id: str) -> ConsensusResult:
        """Get the result of a proposal."""
        proposal = await self._store.get_proposal(proposal_id)
        
        if not proposal:
            return ConsensusResult(
                accepted=False,
                key="",
                error=f"Unknown proposal: {proposal_id}",
            )
        
        votes_for = sum(
            1 for v in proposal.votes if v.vote_type == VoteType.APPROVE
        )
        votes_against = sum(
            1 for v in proposal.votes if v.vote_type == VoteType.REJECT
        )
        
        return ConsensusResult(
            accepted=proposal.state == ProposalState.ACCEPTED,
            key=proposal.key,
            value=proposal.value if proposal.state == ProposalState.ACCEPTED else None,
            votes_for=votes_for,
            votes_against=votes_against,
            total_voters=len(self._voters),
        )
    
    async def is_accepted(self, proposal_id: str) -> bool:
        """Check if a proposal is accepted."""
        result = await self.get_result(proposal_id)
        return result.accepted


# ---------------------------------------------------------------------------
# Transports (how nodes talk to each other)
# ---------------------------------------------------------------------------

RpcHandler = Callable[[Dict[str, Any]], "asyncio.Future[Dict[str, Any]] | Dict[str, Any]"]


class ConsensusTransport(ABC):
    """Delivers RPC messages between consensus nodes."""
    
    @abstractmethod
    async def send(self, target: str, message: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        """Deliver ``message`` to ``target`` and return its reply. Raises on failure."""
    
    @abstractmethod
    def register(self, node_id: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """Register the local node's RPC handler."""


class InMemoryTransport(ConsensusTransport):
    """Process-local transport; share one instance between nodes of a test cluster.

    ``partition(a, b)`` injects a network partition between two nodes and
    ``heal()`` removes all injected partitions.
    """
    
    def __init__(self, latency: float = 0.0):
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._blocked: Set[frozenset] = set()
        self._latency = latency
    
    def register(self, node_id: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        self._handlers[node_id] = handler
    
    def partition(self, a: str, b: str) -> None:
        self._blocked.add(frozenset((a, b)))
    
    def heal(self) -> None:
        self._blocked.clear()
    
    async def send(self, target: str, message: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        handler = self._handlers.get(target)
        if handler is None:
            raise ConsensusError(f"Node {target} unreachable")
        if frozenset((message.get("from"), target)) in self._blocked:
            raise ConsensusError(f"Network partition between {message.get('from')} and {target}")
        if self._latency:
            await asyncio.sleep(self._latency)
        result = handler(dict(message))
        if asyncio.iscoroutine(result):
            result = await asyncio.wait_for(result, timeout)
        return result


class HTTPTransport(ConsensusTransport):
    """HTTP transport: ``peers`` maps node id -> base URL; RPCs are POSTed to ``/consensus/rpc``.

    Call :meth:`mount` on an :class:`agenticaiframework._internal.http_server.App`
    (or any router with ``post(path)``) to expose the local node.
    """
    
    PATH = "/consensus/rpc"
    
    def __init__(self, peers: Dict[str, str], *, shared_secret: Optional[str] = None):
        self._peers = {k: v.rstrip("/") for k, v in peers.items()}
        self._secret = shared_secret
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
    
    def register(self, node_id: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        self._handlers[node_id] = handler
    
    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._secret:
            headers["X-Consensus-Token"] = self._secret
        return headers
    
    async def send(self, target: str, message: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        from agenticaiframework._internal.http import AsyncClient
        
        base = self._peers.get(target)
        if base is None:
            raise ConsensusError(f"Unknown peer {target}")
        resp = await AsyncClient(timeout=timeout).post(base + self.PATH, json=message, headers=self._headers(), timeout=timeout)
        if not resp.ok:
            raise ConsensusError(f"{target} returned HTTP {resp.status}")
        return resp.json()
    
    async def dispatch(self, message: Dict[str, Any], token: Optional[str] = None) -> Dict[str, Any]:
        """Route an inbound RPC (from any HTTP framework) to the local node."""
        if self._secret and token != self._secret:
            raise PermissionError("invalid consensus token")
        target = message.get("to")
        handler = self._handlers.get(target) if target else next(iter(self._handlers.values()), None)
        if handler is None:
            raise ConsensusError(f"No local node for {target}")
        result = handler(message)
        if asyncio.iscoroutine(result):
            result = await result
        return result
    
    def mount(self, app: Any) -> None:
        """Expose the RPC endpoint on an ``_internal.http_server.App``-style router."""
        from agenticaiframework._internal.http_server import Response
        
        @app.post(self.PATH)
        def _rpc(request):  # pragma: no cover - exercised via real HTTP
            try:
                result = asyncio.run(self.dispatch(request.json(), request.header("X-Consensus-Token")))
                return Response.json(result)
            except PermissionError as e:
                return Response.json({"error": str(e)}, status=403)
            except Exception as e:  # noqa: BLE001
                return Response.json({"error": str(e)}, status=500)


class ConsensusGroup:
    """
    Consensus group for distributed agreement.

    Proposals are sent to every node through the ``transport``; each node's
    ``vote_handler(proposal) -> bool`` decides its vote (default: approve).
    Without a transport the group is single-node and only the local vote counts.
    """
    
    def __init__(
        self,
        group_id: str,
        node_id: str,
        nodes: List[str],
        store: ProposalStore,
        config: Optional[ConsensusConfig] = None,
        transport: Optional[ConsensusTransport] = None,
        vote_handler: Optional[Callable[[Proposal], Any]] = None,
    ):
        self._group_id = group_id
        self._node_id = node_id
        self._nodes = set(nodes) | {node_id}
        self._store = store
        self._config = config or ConsensusConfig()
        self._calculator = QuorumCalculator(
            self._config.quorum_type,
            self._config.custom_quorum_threshold,
        )
        self._transport = transport
        self._vote_handler = vote_handler
        self._state = ConsensusState.FOLLOWER
        self._term = 0
        self._voted_for: Optional[str] = None
        self._log: List[Dict[str, Any]] = []
        self._commit_index = 0
        self._callbacks: List[Callable[[str, Any], None]] = []
        if transport is not None:
            transport.register(node_id, self.handle_rpc)
    
    @property
    def group_id(self) -> str:
        return self._group_id
    
    @property
    def node_id(self) -> str:
        return self._node_id
    
    @property
    def state(self) -> ConsensusState:
        return self._state
    
    @property
    def term(self) -> int:
        return self._term
    
    @property
    def is_leader(self) -> bool:
        return self._state == ConsensusState.LEADER
    
    @property
    def committed_log(self) -> List[Dict[str, Any]]:
        return list(self._log[:self._commit_index])
    
    def on_commit(
        self,
        callback: Callable[[str, Any], None],
    ) -> Callable[[], None]:
        """Register callback for committed entries."""
        self._callbacks.append(callback)
        
        def unregister():
            self._callbacks.remove(callback)
        
        return unregister
    
    # -- RPC surface -----------------------------------------------------------
    
    async def handle_rpc(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an inbound message from a peer."""
        kind = message.get("type")
        if kind == "vote_request":
            proposal = Proposal(
                proposal_id=message["proposal_id"],
                proposer_id=message["from"],
                key=message["key"],
                value=message["value"],
                expires_at=datetime.fromisoformat(message["expires_at"]) if message.get("expires_at") else None,
            )
            approve = await self._decide(proposal)
            return {"type": "vote", "from": self._node_id, "proposal_id": proposal.proposal_id, "approve": approve}
        if kind == "commit":
            entry = {"key": message["key"], "value": message["value"], "term": message.get("term", 0),
                     "proposal_id": message.get("proposal_id")}
            self._log.append(entry)
            self._commit_index = len(self._log)
            await self._notify(entry["key"], entry["value"])
            return {"type": "ack", "from": self._node_id}
        return {"type": "error", "error": f"unknown message type {kind!r}"}
    
    async def _decide(self, proposal: Proposal) -> bool:
        if self._vote_handler is None:
            return True
        try:
            verdict = self._vote_handler(proposal)
            if asyncio.iscoroutine(verdict):
                verdict = await verdict
            return bool(verdict)
        except Exception as e:  # noqa: BLE001 - a failing policy is a rejection
            logger.warning(f"vote_handler raised for {proposal.proposal_id}: {e}")
            return False
    
    async def _notify(self, key: str, value: Any) -> None:
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(key, value)
                else:
                    callback(key, value)
            except Exception as e:  # noqa: BLE001
                logger.error(f"Callback error: {e}")
    
    # -- proposing ---------------------------------------------------------------
    
    async def propose(
        self,
        key: str,
        value: Any,
        timeout: Optional[float] = None,
    ) -> ConsensusResult:
        """Propose a value; collects votes from all nodes and commits on quorum."""
        timeout = timeout or self._config.proposal_timeout_seconds
        
        proposal = Proposal(
            proposal_id=str(uuid.uuid4()),
            proposer_id=self._node_id,
            key=key,
            value=value,
            expires_at=datetime.now() + timedelta(seconds=timeout),
        )
        await self._store.save_proposal(proposal)
        
        # Local vote
        local_ok = await self._decide(proposal)
        await self._internal_vote(proposal.proposal_id, self._node_id, local_ok)
        votes_for = 1 if local_ok else 0
        votes_against = 0 if local_ok else 1
        
        # Remote votes (concurrently, bounded by the voting timeout)
        remote = [n for n in self._nodes if n != self._node_id]
        if remote and self._transport is not None:
            message = {
                "type": "vote_request", "from": self._node_id, "group": self._group_id,
                "proposal_id": proposal.proposal_id, "key": key, "value": value,
                "expires_at": proposal.expires_at.isoformat() if proposal.expires_at else None,
            }
            replies = await asyncio.gather(*(
                self._transport.send(n, {**message, "to": n}, self._config.voting_timeout_seconds) for n in remote
            ), return_exceptions=True)
            for node, reply in zip(remote, replies):
                if isinstance(reply, Exception):
                    logger.warning(f"Vote from {node} failed: {reply}")
                    continue
                approve = bool(reply.get("approve"))
                await self._internal_vote(proposal.proposal_id, node, approve)
                if approve:
                    votes_for += 1
                else:
                    votes_against += 1
        elif remote:
            logger.debug("No transport configured; remote nodes %s cannot vote", remote)
        
        total = len(self._nodes)
        accepted = self._calculator.is_quorum_reached(votes_for, total)
        await self._store.update_state(
            proposal.proposal_id,
            ProposalState.ACCEPTED if accepted else ProposalState.REJECTED,
        )
        
        if accepted:
            entry = {"key": key, "value": value, "term": self._term, "proposal_id": proposal.proposal_id}
            self._log.append(entry)
            self._commit_index = len(self._log)
            await self._notify(key, value)
            if remote and self._transport is not None:
                commit_msg = {"type": "commit", "from": self._node_id, "group": self._group_id,
                              "proposal_id": proposal.proposal_id, "key": key, "value": value, "term": self._term}
                await asyncio.gather(*(
                    self._transport.send(n, {**commit_msg, "to": n}, self._config.voting_timeout_seconds) for n in remote
                ), return_exceptions=True)
        
        return ConsensusResult(
            accepted=accepted,
            key=key,
            value=value if accepted else None,
            votes_for=votes_for,
            votes_against=votes_against,
            total_voters=total,
            term=self._term,
            error=None if accepted else f"quorum not reached ({votes_for}/{total})",
        )
    
    async def _internal_vote(
        self,
        proposal_id: str,
        voter_id: str,
        approve: bool,
    ) -> None:
        """Record a vote in the proposal store."""
        proposal = await self._store.get_proposal(proposal_id)
        if proposal:
            vote = Vote(
                voter_id=voter_id,
                proposal_id=proposal_id,
                vote_type=VoteType.APPROVE if approve else VoteType.REJECT,
            )
            await self._store.add_vote(proposal_id, vote)


class RaftConsensus:
    """
    Raft consensus (leader election + log replication) over a
    :class:`ConsensusTransport`.

    A single node with no peers elects itself immediately; multi-node clusters
    need a shared transport (``InMemoryTransport`` in-process, ``HTTPTransport``
    across hosts). Committed entries are applied to a key/value state machine.
    """
    
    def __init__(
        self,
        node_id: str,
        peers: List[str],
        config: Optional[ConsensusConfig] = None,
        transport: Optional[ConsensusTransport] = None,
    ):
        self._node_id = node_id
        self._peers = set(peers) - {node_id}
        self._config = config or ConsensusConfig()
        self._transport = transport
        
        self._state = ConsensusState.FOLLOWER
        self._term = 0
        self._voted_for: Optional[str] = None
        self._leader_id: Optional[str] = None
        
        # Log: 1-based indices; each entry has term/key/value/index
        self._log: List[Dict[str, Any]] = []
        self._commit_index = 0
        self._last_applied = 0
        self._next_index: Dict[str, int] = {}
        self._match_index: Dict[str, int] = {}
        
        self._state_machine: Dict[str, Any] = {}
        self._commit_waiters: Dict[int, List[asyncio.Future]] = {}
        self._apply_callbacks: List[Callable[[str, Any], Any]] = []
        
        self._election_timeout = self._random_timeout()
        self._last_heartbeat = time.time()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        if transport is not None:
            transport.register(node_id, self.handle_rpc)
    
    # -- properties ------------------------------------------------------------------
    
    def _random_timeout(self) -> float:
        base = self._config.election_timeout_ms / 1000
        return base + random.random() * base
    
    @property
    def node_id(self) -> str:
        return self._node_id
    
    @property
    def state(self) -> ConsensusState:
        return self._state
    
    @property
    def term(self) -> int:
        return self._term
    
    @property
    def is_leader(self) -> bool:
        return self._state == ConsensusState.LEADER
    
    @property
    def leader_id(self) -> Optional[str]:
        return self._leader_id
    
    @property
    def commit_index(self) -> int:
        return self._commit_index
    
    @property
    def log(self) -> List[Dict[str, Any]]:
        return list(self._log)
    
    def on_apply(self, callback: Callable[[str, Any], Any]) -> None:
        """Register a callback invoked when an entry is applied to the state machine."""
        self._apply_callbacks.append(callback)
    
    def _last_log(self) -> "tuple[int, int]":
        if not self._log:
            return 0, 0
        return len(self._log), self._log[-1]["term"]
    
    def _quorum(self) -> int:
        return (len(self._peers) + 1) // 2 + 1
    
    # -- lifecycle -----------------------------------------------------------------------
    
    async def start(self) -> None:
        """Start the consensus node."""
        self._running = True
        self._last_heartbeat = time.time()
        self._task = asyncio.create_task(self._run_loop())
    
    async def stop(self) -> None:
        """Stop the consensus node."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
    
    async def _run_loop(self) -> None:
        while self._running:
            try:
                if self._state == ConsensusState.FOLLOWER:
                    await self._follower_loop()
                elif self._state == ConsensusState.CANDIDATE:
                    await self._candidate_loop()
                elif self._state == ConsensusState.LEADER:
                    await self._leader_loop()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.error(f"Consensus error on {self._node_id}: {e}")
                await asyncio.sleep(0.1)
    
    async def _follower_loop(self) -> None:
        if time.time() - self._last_heartbeat > self._election_timeout:
            self._become_candidate()
            return
        await asyncio.sleep(min(0.05, self._election_timeout / 10))
    
    def _become_candidate(self) -> None:
        self._state = ConsensusState.CANDIDATE
        self._term += 1
        self._voted_for = self._node_id
        self._leader_id = None
        self._election_timeout = self._random_timeout()
        self._last_heartbeat = time.time()
        logger.info(f"Node {self._node_id} becoming candidate, term {self._term}")
    
    def _become_follower(self, term: int, leader: Optional[str] = None) -> None:
        if term > self._term:
            self._term = term
            self._voted_for = None
        self._state = ConsensusState.FOLLOWER
        if leader:
            self._leader_id = leader
        self._last_heartbeat = time.time()
        self._election_timeout = self._random_timeout()
    
    def _become_leader(self) -> None:
        self._state = ConsensusState.LEADER
        self._leader_id = self._node_id
        last_index, _ = self._last_log()
        self._next_index = {p: last_index + 1 for p in self._peers}
        self._match_index = {p: 0 for p in self._peers}
        logger.info(f"Node {self._node_id} became leader, term {self._term}")
    
    async def _candidate_loop(self) -> None:
        term = self._term
        votes = 1
        if self._peers and self._transport is not None:
            last_index, last_term = self._last_log()
            request = {"type": "request_vote", "from": self._node_id, "term": term,
                       "candidate_id": self._node_id, "last_log_index": last_index, "last_log_term": last_term}
            timeout = max(0.2, self._config.election_timeout_ms / 2000)
            replies = await asyncio.gather(*(
                self._transport.send(p, {**request, "to": p}, timeout) for p in self._peers
            ), return_exceptions=True)
            for reply in replies:
                if isinstance(reply, Exception) or not isinstance(reply, dict):
                    continue
                if reply.get("term", 0) > self._term:
                    self._become_follower(reply["term"])
                    return
                if reply.get("vote_granted"):
                    votes += 1
        if self._state != ConsensusState.CANDIDATE or self._term != term:
            return
        if votes >= self._quorum():
            self._become_leader()
            await self._replicate()  # immediate heartbeat asserts leadership
        else:
            # Split vote / partition: back off with a fresh randomized timeout.
            await asyncio.sleep(self._random_timeout())
            if self._state == ConsensusState.CANDIDATE:
                self._become_candidate()
    
    async def _leader_loop(self) -> None:
        await self._replicate()
        await asyncio.sleep(self._config.heartbeat_interval_ms / 1000)
    
    # -- replication -----------------------------------------------------------------------
    
    async def _replicate(self) -> None:
        """Send AppendEntries (with any missing entries) to every peer and advance commit index."""
        if not self._peers or self._transport is None:
            self._advance_commit_index()
            return
        timeout = max(0.2, self._config.heartbeat_interval_ms / 1000)
        
        async def one(peer: str) -> None:
            next_idx = self._next_index.get(peer, len(self._log) + 1)
            prev_index = next_idx - 1
            prev_term = self._log[prev_index - 1]["term"] if prev_index > 0 and prev_index <= len(self._log) else 0
            entries = self._log[next_idx - 1:]
            msg = {"type": "append_entries", "from": self._node_id, "to": peer, "term": self._term,
                   "leader_id": self._node_id, "prev_log_index": prev_index, "prev_log_term": prev_term,
                   "entries": entries, "leader_commit": self._commit_index}
            try:
                reply = await self._transport.send(peer, msg, timeout)
            except Exception as e:  # noqa: BLE001 - unreachable peer, retry next heartbeat
                logger.debug(f"AppendEntries to {peer} failed: {e}")
                return
            if not isinstance(reply, dict):
                return
            if reply.get("term", 0) > self._term:
                self._become_follower(reply["term"])
                return
            if reply.get("success"):
                match = int(reply.get("match_index", prev_index + len(entries)))
                self._match_index[peer] = max(self._match_index.get(peer, 0), match)
                self._next_index[peer] = self._match_index[peer] + 1
            else:
                # Consistency check failed: back off (use follower hint when provided).
                hint = reply.get("conflict_index")
                self._next_index[peer] = max(1, int(hint) if hint else next_idx - 1)
        
        await asyncio.gather(*(one(p) for p in self._peers))
        if self._state == ConsensusState.LEADER:
            self._advance_commit_index()
    
    def _advance_commit_index(self) -> None:
        last_index = len(self._log)
        for n in range(last_index, self._commit_index, -1):
            if self._log[n - 1]["term"] != self._term:
                continue
            replicated = 1 + sum(1 for p in self._peers if self._match_index.get(p, 0) >= n)
            if replicated >= self._quorum():
                self._commit_index = n
                break
        self._apply_committed()
    
    def _apply_committed(self) -> None:
        while self._last_applied < self._commit_index:
            self._last_applied += 1
            entry = self._log[self._last_applied - 1]
            self._state_machine[entry["key"]] = entry["value"]
            for cb in self._apply_callbacks:
                try:
                    cb(entry["key"], entry["value"])
                except Exception as e:  # noqa: BLE001
                    logger.error(f"apply callback error: {e}")
            for fut in self._commit_waiters.pop(self._last_applied, []):
                if not fut.done():
                    fut.set_result(True)
    
    # -- RPC handlers ----------------------------------------------------------------------------
    
    async def handle_rpc(self, message: Dict[str, Any]) -> Dict[str, Any]:
        kind = message.get("type")
        if kind == "request_vote":
            return self._on_request_vote(message)
        if kind == "append_entries":
            return self._on_append_entries(message)
        if kind == "client_command":
            result = await self.apply_command(message["key"], message["value"])
            return {"accepted": result.accepted, "error": result.error, "leader_id": self._leader_id}
        return {"error": f"unknown rpc {kind!r}", "term": self._term}
    
    def _on_request_vote(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        term = int(msg.get("term", 0))
        if term > self._term:
            self._become_follower(term)
        granted = False
        if term == self._term and self._voted_for in (None, msg.get("candidate_id")):
            last_index, last_term = self._last_log()
            up_to_date = (msg.get("last_log_term", 0), msg.get("last_log_index", 0)) >= (last_term, last_index)
            if up_to_date:
                granted = True
                self._voted_for = msg.get("candidate_id")
                self._last_heartbeat = time.time()
        return {"type": "request_vote_reply", "from": self._node_id, "term": self._term, "vote_granted": granted}
    
    def _on_append_entries(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        term = int(msg.get("term", 0))
        if term < self._term:
            return {"type": "append_entries_reply", "from": self._node_id, "term": self._term, "success": False}
        self._become_follower(term, leader=msg.get("leader_id"))
        prev_index = int(msg.get("prev_log_index", 0))
        prev_term = int(msg.get("prev_log_term", 0))
        if prev_index > len(self._log):
            return {"type": "append_entries_reply", "from": self._node_id, "term": self._term, "success": False,
                    "conflict_index": len(self._log) + 1}
        if prev_index > 0 and self._log[prev_index - 1]["term"] != prev_term:
            conflict_term = self._log[prev_index - 1]["term"]
            first = next(i for i, e in enumerate(self._log, start=1) if e["term"] == conflict_term)
            del self._log[prev_index - 1:]
            return {"type": "append_entries_reply", "from": self._node_id, "term": self._term, "success": False,
                    "conflict_index": first}
        entries = msg.get("entries") or []
        for offset, entry in enumerate(entries):
            idx = prev_index + offset + 1
            if idx <= len(self._log):
                if self._log[idx - 1]["term"] != entry["term"]:
                    del self._log[idx - 1:]
                    self._log.append(entry)
            else:
                self._log.append(entry)
        leader_commit = int(msg.get("leader_commit", 0))
        if leader_commit > self._commit_index:
            self._commit_index = min(leader_commit, len(self._log))
            self._apply_committed()
        return {"type": "append_entries_reply", "from": self._node_id, "term": self._term, "success": True,
                "match_index": prev_index + len(entries)}
    
    # -- client API ---------------------------------------------------------------------------------
    
    async def apply_command(
        self,
        key: str,
        value: Any,
        timeout: Optional[float] = None,
    ) -> ConsensusResult:
        """Append a command to the replicated log and wait until it is committed."""
        if not self.is_leader:
            if self._leader_id and self._transport is not None and self._leader_id != self._node_id:
                try:
                    reply = await self._transport.send(
                        self._leader_id,
                        {"type": "client_command", "from": self._node_id, "to": self._leader_id, "key": key, "value": value},
                        timeout or self._config.proposal_timeout_seconds,
                    )
                    return ConsensusResult(accepted=bool(reply.get("accepted")), key=key,
                                           value=value if reply.get("accepted") else None,
                                           error=reply.get("error"), term=self._term)
                except Exception as e:  # noqa: BLE001
                    return ConsensusResult(accepted=False, key=key, error=f"forward to leader failed: {e}")
            return ConsensusResult(accepted=False, key=key, error="Not the leader")
        
        entry = {"term": self._term, "key": key, "value": value, "index": len(self._log) + 1}
        self._log.append(entry)
        index = entry["index"]
        
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._commit_waiters.setdefault(index, []).append(fut)
        await self._replicate()
        try:
            await asyncio.wait_for(fut, timeout or self._config.proposal_timeout_seconds)
        except asyncio.TimeoutError:
            return ConsensusResult(accepted=False, key=key, error="commit timeout", term=self._term,
                                   votes_for=1 + sum(1 for p in self._peers if self._match_index.get(p, 0) >= index),
                                   total_voters=len(self._peers) + 1)
        # Push the new commit index to followers right away instead of waiting a heartbeat.
        if self.is_leader:
            await self._replicate()
        
        return ConsensusResult(
            accepted=True,
            key=key,
            value=value,
            votes_for=1 + sum(1 for p in self._peers if self._match_index.get(p, 0) >= index),
            votes_against=0,
            total_voters=len(self._peers) + 1,
            term=self._term,
        )
    
    def get_value(self, key: str) -> Optional[Any]:
        """Get value from state machine."""
        return self._state_machine.get(key)
    
    def snapshot(self) -> Dict[str, Any]:
        """Copy of the applied state machine."""
        return dict(self._state_machine)


# Decorators
def requires_consensus(
    group: ConsensusGroup,
) -> Callable:
    """
    Decorator to require consensus before execution.
    
    Example:
        @requires_consensus(group)
        async def critical_operation(data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Create proposal hash from function and args
            proposal_key = hashlib.md5(
                f"{func.__name__}:{args}:{kwargs}".encode()
            ).hexdigest()[:16]
            
            result = await group.propose(
                proposal_key,
                {"func": func.__name__, "args": args, "kwargs": kwargs},
            )
            
            if not result.accepted:
                raise ProposalRejectedError(
                    f"Consensus not reached for {func.__name__}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def with_quorum(
    quorum: Quorum,
    voter_id: str,
) -> Callable:
    """
    Decorator for quorum-based execution.
    
    Example:
        @with_quorum(quorum, "voter_1")
        async def collective_decision(action):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Create proposal
            proposal = await quorum.create_proposal(
                func.__name__,
                {"args": args, "kwargs": kwargs},
                voter_id,
            )
            
            # Auto-vote approve
            await quorum.vote(proposal.proposal_id, voter_id, approve=True)
            
            # Check result after brief delay
            await asyncio.sleep(0.1)
            
            if await quorum.is_accepted(proposal.proposal_id):
                return await func(*args, **kwargs)
            
            raise ProposalRejectedError(
                f"Quorum not reached for {func.__name__}"
            )
        
        return wrapper
    
    return decorator


# Factory functions
def create_quorum(
    quorum_id: str,
    voters: List[str],
    quorum_type: QuorumType = QuorumType.SIMPLE_MAJORITY,
) -> Quorum:
    """Create a quorum."""
    store = InMemoryProposalStore()
    calculator = QuorumCalculator(quorum_type)
    return Quorum(quorum_id, voters, store, calculator)


def create_consensus_group(
    group_id: str,
    nodes: List[str],
    node_id: Optional[str] = None,
    transport: Optional[ConsensusTransport] = None,
    vote_handler: Optional[Callable[[Proposal], Any]] = None,
) -> ConsensusGroup:
    """Create a consensus group."""
    nid = node_id or (nodes[0] if nodes else str(uuid.uuid4()))
    store = InMemoryProposalStore()
    return ConsensusGroup(group_id, nid, nodes, store, transport=transport, vote_handler=vote_handler)


def create_raft_consensus(
    node_id: str,
    peers: List[str],
    transport: Optional[ConsensusTransport] = None,
    config: Optional[ConsensusConfig] = None,
) -> RaftConsensus:
    """Create a Raft consensus node."""
    return RaftConsensus(node_id, peers, config=config, transport=transport)


def create_quorum_calculator(
    quorum_type: QuorumType = QuorumType.SIMPLE_MAJORITY,
    custom_threshold: float = 0.5,
) -> QuorumCalculator:
    """Create a quorum calculator."""
    return QuorumCalculator(quorum_type, custom_threshold)


__all__ = [
    # Exceptions
    "ConsensusError",
    "NoQuorumError",
    "ProposalRejectedError",
    # Enums
    "ConsensusState",
    "VoteType",
    "ProposalState",
    "QuorumType",
    # Data classes
    "Vote",
    "Proposal",
    "ConsensusResult",
    "NodeInfo",
    "ConsensusConfig",
    # Stores
    "ProposalStore",
    "InMemoryProposalStore",
    # Core classes
    "QuorumCalculator",
    "Quorum",
    "ConsensusGroup",
    "RaftConsensus",
    # Transports
    "ConsensusTransport",
    "InMemoryTransport",
    "HTTPTransport",
    # Decorators
    "requires_consensus",
    "with_quorum",
    # Factory functions
    "create_quorum",
    "create_consensus_group",
    "create_raft_consensus",
    "create_quorum_calculator",
]
