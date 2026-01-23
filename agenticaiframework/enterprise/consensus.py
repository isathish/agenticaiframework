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


class ConsensusGroup:
    """
    Consensus group for distributed agreement.
    """
    
    def __init__(
        self,
        group_id: str,
        node_id: str,
        nodes: List[str],
        store: ProposalStore,
        config: Optional[ConsensusConfig] = None,
    ):
        self._group_id = group_id
        self._node_id = node_id
        self._nodes = set(nodes)
        self._store = store
        self._config = config or ConsensusConfig()
        self._calculator = QuorumCalculator(
            self._config.quorum_type,
            self._config.custom_quorum_threshold,
        )
        self._state = ConsensusState.FOLLOWER
        self._term = 0
        self._voted_for: Optional[str] = None
        self._log: List[Dict[str, Any]] = []
        self._commit_index = 0
        self._callbacks: List[Callable[[str, Any], None]] = []
    
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
    
    def on_commit(
        self,
        callback: Callable[[str, Any], None],
    ) -> Callable[[], None]:
        """Register callback for committed entries."""
        self._callbacks.append(callback)
        
        def unregister():
            self._callbacks.remove(callback)
        
        return unregister
    
    async def propose(
        self,
        key: str,
        value: Any,
        timeout: Optional[float] = None,
    ) -> ConsensusResult:
        """
        Propose a value for consensus.
        """
        timeout = timeout or self._config.proposal_timeout_seconds
        
        # Create proposal
        proposal = await self._store.save_proposal(
            Proposal(
                proposal_id=str(uuid.uuid4()),
                proposer_id=self._node_id,
                key=key,
                value=value,
                expires_at=datetime.now() + timedelta(seconds=timeout),
            )
        )
        
        # Auto-vote as proposer
        await self._internal_vote(
            proposal.proposal_id if hasattr(proposal, 'proposal_id') else str(uuid.uuid4()),
            self._node_id,
            True,
        )
        
        # Simulate other nodes voting (in real impl, this would be network calls)
        for node in self._nodes:
            if node != self._node_id:
                # Simple: all nodes approve (replace with actual node communication)
                await self._internal_vote(
                    proposal.proposal_id if hasattr(proposal, 'proposal_id') else str(uuid.uuid4()),
                    node,
                    True,
                )
        
        # Check result
        votes_for = len(self._nodes)
        accepted = self._calculator.is_quorum_reached(votes_for, len(self._nodes))
        
        if accepted:
            # Add to log
            self._log.append({"key": key, "value": value, "term": self._term})
            self._commit_index = len(self._log)
            
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(key, value)
                    else:
                        callback(key, value)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
        
        return ConsensusResult(
            accepted=accepted,
            key=key,
            value=value if accepted else None,
            votes_for=votes_for,
            votes_against=0,
            total_voters=len(self._nodes),
            term=self._term,
        )
    
    async def _internal_vote(
        self,
        proposal_id: str,
        voter_id: str,
        approve: bool,
    ) -> None:
        """Internal vote processing."""
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
    Simplified Raft consensus implementation.
    """
    
    def __init__(
        self,
        node_id: str,
        peers: List[str],
        config: Optional[ConsensusConfig] = None,
    ):
        self._node_id = node_id
        self._peers = set(peers)
        self._config = config or ConsensusConfig()
        
        self._state = ConsensusState.FOLLOWER
        self._term = 0
        self._voted_for: Optional[str] = None
        self._leader_id: Optional[str] = None
        
        # Log
        self._log: List[Dict[str, Any]] = []
        self._commit_index = 0
        self._last_applied = 0
        
        # State machine
        self._state_machine: Dict[str, Any] = {}
        
        # Timers
        self._election_timeout = self._random_timeout()
        self._last_heartbeat = time.time()
        self._running = False
    
    def _random_timeout(self) -> float:
        """Generate random election timeout."""
        base = self._config.election_timeout_ms / 1000
        return base + random.random() * base
    
    @property
    def is_leader(self) -> bool:
        return self._state == ConsensusState.LEADER
    
    @property
    def leader_id(self) -> Optional[str]:
        return self._leader_id
    
    async def start(self) -> None:
        """Start the consensus node."""
        self._running = True
        asyncio.create_task(self._run_loop())
    
    async def stop(self) -> None:
        """Stop the consensus node."""
        self._running = False
    
    async def _run_loop(self) -> None:
        """Main consensus loop."""
        while self._running:
            try:
                if self._state == ConsensusState.FOLLOWER:
                    await self._follower_loop()
                elif self._state == ConsensusState.CANDIDATE:
                    await self._candidate_loop()
                elif self._state == ConsensusState.LEADER:
                    await self._leader_loop()
            except Exception as e:
                logger.error(f"Consensus error: {e}")
                await asyncio.sleep(0.1)
    
    async def _follower_loop(self) -> None:
        """Follower state loop."""
        if time.time() - self._last_heartbeat > self._election_timeout:
            # Timeout, become candidate
            self._state = ConsensusState.CANDIDATE
            self._term += 1
            self._voted_for = self._node_id
            logger.info(f"Node {self._node_id} becoming candidate, term {self._term}")
        
        await asyncio.sleep(0.1)
    
    async def _candidate_loop(self) -> None:
        """Candidate state loop."""
        # Request votes from peers (simplified)
        votes = 1  # Vote for self
        
        # In real implementation, send RequestVote RPCs to peers
        # For now, simulate winning election if we're the only node
        # or if we get majority
        
        quorum = (len(self._peers) + 1) // 2 + 1
        
        if votes >= quorum:
            self._state = ConsensusState.LEADER
            self._leader_id = self._node_id
            logger.info(f"Node {self._node_id} became leader, term {self._term}")
        else:
            # Failed, restart timeout
            self._election_timeout = self._random_timeout()
            self._state = ConsensusState.FOLLOWER
        
        await asyncio.sleep(0.1)
    
    async def _leader_loop(self) -> None:
        """Leader state loop."""
        # Send heartbeats (in real impl, AppendEntries RPCs)
        await asyncio.sleep(self._config.heartbeat_interval_ms / 1000)
    
    async def apply_command(
        self,
        key: str,
        value: Any,
    ) -> ConsensusResult:
        """Apply a command to the state machine."""
        if not self.is_leader:
            return ConsensusResult(
                accepted=False,
                key=key,
                error="Not the leader",
            )
        
        # Append to log
        entry = {
            "term": self._term,
            "key": key,
            "value": value,
            "index": len(self._log) + 1,
        }
        self._log.append(entry)
        
        # In real implementation, replicate to followers
        # For now, immediately commit
        self._commit_index = len(self._log)
        self._state_machine[key] = value
        self._last_applied = self._commit_index
        
        return ConsensusResult(
            accepted=True,
            key=key,
            value=value,
            votes_for=len(self._peers) + 1,
            votes_against=0,
            total_voters=len(self._peers) + 1,
            term=self._term,
        )
    
    def get_value(self, key: str) -> Optional[Any]:
        """Get value from state machine."""
        return self._state_machine.get(key)


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
) -> ConsensusGroup:
    """Create a consensus group."""
    nid = node_id or nodes[0] if nodes else str(uuid.uuid4())
    store = InMemoryProposalStore()
    return ConsensusGroup(group_id, nid, nodes, store)


def create_raft_consensus(
    node_id: str,
    peers: List[str],
) -> RaftConsensus:
    """Create a Raft consensus node."""
    return RaftConsensus(node_id, peers)


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
    # Decorators
    "requires_consensus",
    "with_quorum",
    # Factory functions
    "create_quorum",
    "create_consensus_group",
    "create_raft_consensus",
    "create_quorum_calculator",
]
