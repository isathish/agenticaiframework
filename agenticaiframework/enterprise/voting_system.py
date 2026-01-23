"""
Enterprise Voting System Module.

Polls, elections, ranked choice voting, ballots,
and vote management.

Example:
    # Create voting system
    voting = create_voting_system()
    
    # Create poll
    poll = await voting.create_poll(
        title="Best Framework",
        options=["Python", "Java", "Go"],
        voting_type=VotingType.SINGLE_CHOICE,
    )
    
    # Cast vote
    vote = await voting.cast_vote(
        poll_id=poll.id,
        voter_id="user_123",
        choice="Python",
    )
    
    # Get results
    results = await voting.get_results(poll.id)
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class VotingError(Exception):
    """Voting error."""
    pass


class PollNotFoundError(VotingError):
    """Poll not found."""
    pass


class VotingNotAllowedError(VotingError):
    """Voting not allowed."""
    pass


class VotingType(str, Enum):
    """Voting type."""
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    RANKED_CHOICE = "ranked_choice"
    APPROVAL = "approval"
    SCORE = "score"
    YES_NO = "yes_no"


class PollStatus(str, Enum):
    """Poll status."""
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class VoteStatus(str, Enum):
    """Vote status."""
    VALID = "valid"
    INVALID = "invalid"
    ABSTAIN = "abstain"


@dataclass
class PollOption:
    """Poll option."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    description: str = ""
    image_url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Poll:
    """Poll definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: PollStatus = PollStatus.DRAFT
    voting_type: VotingType = VotingType.SINGLE_CHOICE
    options: List[PollOption] = field(default_factory=list)
    anonymous: bool = False
    allow_change_vote: bool = False
    max_choices: int = 1
    min_choices: int = 1
    max_score: int = 5  # For score voting
    show_results_before_close: bool = False
    require_all_ranks: bool = False  # For ranked choice
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    eligible_voters: List[str] = field(default_factory=list)  # Empty = all allowed
    voter_count: int = 0
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Vote:
    """Vote record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    poll_id: str = ""
    voter_id: str = ""
    voter_hash: str = ""  # Anonymized voter ID
    status: VoteStatus = VoteStatus.VALID
    choices: List[str] = field(default_factory=list)  # Option IDs
    rankings: Dict[str, int] = field(default_factory=dict)  # Option ID -> rank
    scores: Dict[str, int] = field(default_factory=dict)  # Option ID -> score
    ip_address: str = ""
    user_agent: str = ""
    cast_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PollResults:
    """Poll results."""
    poll_id: str = ""
    poll_title: str = ""
    voting_type: VotingType = VotingType.SINGLE_CHOICE
    total_votes: int = 0
    valid_votes: int = 0
    invalid_votes: int = 0
    abstain_votes: int = 0
    option_counts: Dict[str, int] = field(default_factory=dict)
    option_percentages: Dict[str, float] = field(default_factory=dict)
    option_scores: Dict[str, float] = field(default_factory=dict)
    winner: Optional[str] = None
    winner_label: str = ""
    ranked_results: List[Tuple[str, int]] = field(default_factory=list)
    instant_runoff_rounds: List[Dict[str, int]] = field(default_factory=list)
    is_tie: bool = False
    calculated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VotingStats:
    """Voting statistics."""
    total_polls: int = 0
    active_polls: int = 0
    total_votes: int = 0


# Poll store
class PollStore(ABC):
    """Poll storage."""
    
    @abstractmethod
    async def save(self, poll: Poll) -> None:
        pass
    
    @abstractmethod
    async def get(self, poll_id: str) -> Optional[Poll]:
        pass
    
    @abstractmethod
    async def list(self, status: Optional[PollStatus] = None) -> List[Poll]:
        pass
    
    @abstractmethod
    async def delete(self, poll_id: str) -> bool:
        pass


class InMemoryPollStore(PollStore):
    """In-memory poll store."""
    
    def __init__(self):
        self._polls: Dict[str, Poll] = {}
    
    async def save(self, poll: Poll) -> None:
        poll.updated_at = datetime.utcnow()
        self._polls[poll.id] = poll
    
    async def get(self, poll_id: str) -> Optional[Poll]:
        return self._polls.get(poll_id)
    
    async def list(self, status: Optional[PollStatus] = None) -> List[Poll]:
        polls = list(self._polls.values())
        if status:
            polls = [p for p in polls if p.status == status]
        return sorted(polls, key=lambda p: p.created_at, reverse=True)
    
    async def delete(self, poll_id: str) -> bool:
        return self._polls.pop(poll_id, None) is not None


# Vote store
class VoteStore(ABC):
    """Vote storage."""
    
    @abstractmethod
    async def save(self, vote: Vote) -> None:
        pass
    
    @abstractmethod
    async def get(self, vote_id: str) -> Optional[Vote]:
        pass
    
    @abstractmethod
    async def get_by_voter(self, poll_id: str, voter_id: str) -> Optional[Vote]:
        pass
    
    @abstractmethod
    async def query(self, poll_id: str) -> List[Vote]:
        pass


class InMemoryVoteStore(VoteStore):
    """In-memory vote store."""
    
    def __init__(self):
        self._votes: Dict[str, Vote] = {}
        self._voter_index: Dict[str, Dict[str, str]] = {}  # poll_id -> voter_id -> vote_id
    
    async def save(self, vote: Vote) -> None:
        self._votes[vote.id] = vote
        
        if vote.poll_id not in self._voter_index:
            self._voter_index[vote.poll_id] = {}
        self._voter_index[vote.poll_id][vote.voter_id] = vote.id
    
    async def get(self, vote_id: str) -> Optional[Vote]:
        return self._votes.get(vote_id)
    
    async def get_by_voter(self, poll_id: str, voter_id: str) -> Optional[Vote]:
        vote_id = self._voter_index.get(poll_id, {}).get(voter_id)
        return self._votes.get(vote_id) if vote_id else None
    
    async def query(self, poll_id: str) -> List[Vote]:
        return [v for v in self._votes.values() if v.poll_id == poll_id]


# Voting system
class VotingSystem:
    """Voting system."""
    
    def __init__(
        self,
        poll_store: Optional[PollStore] = None,
        vote_store: Optional[VoteStore] = None,
    ):
        self._polls = poll_store or InMemoryPollStore()
        self._votes = vote_store or InMemoryVoteStore()
        self._stats = VotingStats()
    
    async def create_poll(
        self,
        title: str,
        options: List[str] = None,
        voting_type: VotingType = VotingType.SINGLE_CHOICE,
        description: str = "",
        created_by: str = "",
        **kwargs,
    ) -> Poll:
        """Create poll."""
        poll = Poll(
            title=title,
            description=description,
            voting_type=voting_type,
            created_by=created_by,
            **kwargs,
        )
        
        # Add options
        if options:
            for opt in options:
                if isinstance(opt, dict):
                    poll.options.append(PollOption(**opt))
                else:
                    poll.options.append(PollOption(label=str(opt)))
        
        # Set defaults based on voting type
        if voting_type == VotingType.YES_NO:
            poll.options = [
                PollOption(id="yes", label="Yes"),
                PollOption(id="no", label="No"),
            ]
        
        await self._polls.save(poll)
        self._stats.total_polls += 1
        
        logger.info(f"Poll created: {title}")
        
        return poll
    
    async def get_poll(self, poll_id: str) -> Optional[Poll]:
        """Get poll."""
        return await self._polls.get(poll_id)
    
    async def open_poll(self, poll_id: str) -> Optional[Poll]:
        """Open poll for voting."""
        poll = await self._polls.get(poll_id)
        if not poll:
            return None
        
        poll.status = PollStatus.OPEN
        
        await self._polls.save(poll)
        self._stats.active_polls += 1
        
        logger.info(f"Poll opened: {poll.title}")
        
        return poll
    
    async def close_poll(self, poll_id: str) -> Optional[Poll]:
        """Close poll."""
        poll = await self._polls.get(poll_id)
        if not poll:
            return None
        
        poll.status = PollStatus.CLOSED
        
        await self._polls.save(poll)
        self._stats.active_polls -= 1
        
        logger.info(f"Poll closed: {poll.title}")
        
        return poll
    
    async def cast_vote(
        self,
        poll_id: str,
        voter_id: str,
        choice: Optional[str] = None,
        choices: Optional[List[str]] = None,
        rankings: Optional[Dict[str, int]] = None,
        scores: Optional[Dict[str, int]] = None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> Vote:
        """Cast vote."""
        poll = await self._polls.get(poll_id)
        if not poll:
            raise PollNotFoundError(f"Poll not found: {poll_id}")
        
        if poll.status != PollStatus.OPEN:
            raise VotingNotAllowedError("Poll is not open")
        
        # Check dates
        now = datetime.utcnow()
        if poll.starts_at and now < poll.starts_at:
            raise VotingNotAllowedError("Poll has not started")
        if poll.ends_at and now > poll.ends_at:
            raise VotingNotAllowedError("Poll has ended")
        
        # Check eligibility
        if poll.eligible_voters and voter_id not in poll.eligible_voters:
            raise VotingNotAllowedError("Not eligible to vote")
        
        # Check for existing vote
        existing = await self._votes.get_by_voter(poll_id, voter_id)
        if existing and not poll.allow_change_vote:
            raise VotingNotAllowedError("Already voted")
        
        # Create vote
        vote = Vote(
            poll_id=poll_id,
            voter_id=voter_id,
            voter_hash=hashlib.sha256(voter_id.encode()).hexdigest()[:16],
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Process based on voting type
        option_ids = {opt.id for opt in poll.options}
        
        if poll.voting_type == VotingType.SINGLE_CHOICE or poll.voting_type == VotingType.YES_NO:
            if choice and choice in option_ids:
                vote.choices = [choice]
            else:
                vote.status = VoteStatus.INVALID
        
        elif poll.voting_type == VotingType.MULTIPLE_CHOICE or poll.voting_type == VotingType.APPROVAL:
            if choices:
                valid_choices = [c for c in choices if c in option_ids]
                if len(valid_choices) >= poll.min_choices and len(valid_choices) <= poll.max_choices:
                    vote.choices = valid_choices
                else:
                    vote.status = VoteStatus.INVALID
        
        elif poll.voting_type == VotingType.RANKED_CHOICE:
            if rankings:
                vote.rankings = {k: v for k, v in rankings.items() if k in option_ids}
        
        elif poll.voting_type == VotingType.SCORE:
            if scores:
                vote.scores = {
                    k: min(v, poll.max_score)
                    for k, v in scores.items()
                    if k in option_ids
                }
        
        await self._votes.save(vote)
        
        # Update voter count
        if not existing:
            poll.voter_count += 1
            await self._polls.save(poll)
        
        self._stats.total_votes += 1
        
        logger.info(f"Vote cast on: {poll.title}")
        
        return vote
    
    async def get_results(self, poll_id: str) -> PollResults:
        """Get poll results."""
        poll = await self._polls.get(poll_id)
        if not poll:
            raise PollNotFoundError(f"Poll not found: {poll_id}")
        
        if poll.status == PollStatus.OPEN and not poll.show_results_before_close:
            raise VotingNotAllowedError("Results not available until poll closes")
        
        votes = await self._votes.query(poll_id)
        valid_votes = [v for v in votes if v.status == VoteStatus.VALID]
        
        results = PollResults(
            poll_id=poll_id,
            poll_title=poll.title,
            voting_type=poll.voting_type,
            total_votes=len(votes),
            valid_votes=len(valid_votes),
            invalid_votes=len([v for v in votes if v.status == VoteStatus.INVALID]),
            abstain_votes=len([v for v in votes if v.status == VoteStatus.ABSTAIN]),
        )
        
        # Calculate based on voting type
        if poll.voting_type in (VotingType.SINGLE_CHOICE, VotingType.MULTIPLE_CHOICE, VotingType.YES_NO, VotingType.APPROVAL):
            self._calculate_choice_results(poll, valid_votes, results)
        
        elif poll.voting_type == VotingType.RANKED_CHOICE:
            self._calculate_ranked_results(poll, valid_votes, results)
        
        elif poll.voting_type == VotingType.SCORE:
            self._calculate_score_results(poll, valid_votes, results)
        
        return results
    
    def _calculate_choice_results(
        self,
        poll: Poll,
        votes: List[Vote],
        results: PollResults,
    ):
        """Calculate choice-based results."""
        counter = Counter()
        
        for vote in votes:
            for choice in vote.choices:
                counter[choice] += 1
        
        results.option_counts = dict(counter)
        
        total = sum(counter.values())
        results.option_percentages = {
            k: (v / total * 100) if total > 0 else 0
            for k, v in counter.items()
        }
        
        # Find winner
        if counter:
            winner_id = counter.most_common(1)[0][0]
            results.winner = winner_id
            
            for opt in poll.options:
                if opt.id == winner_id:
                    results.winner_label = opt.label
                    break
            
            # Check for tie
            top_count = counter.most_common(1)[0][1]
            ties = [k for k, v in counter.items() if v == top_count]
            results.is_tie = len(ties) > 1
        
        results.ranked_results = counter.most_common()
    
    def _calculate_ranked_results(
        self,
        poll: Poll,
        votes: List[Vote],
        results: PollResults,
    ):
        """Calculate ranked choice (IRV) results."""
        if not votes:
            return
        
        option_ids = [opt.id for opt in poll.options]
        remaining = set(option_ids)
        rounds: List[Dict[str, int]] = []
        
        # Get first choice counts
        def count_first_choices(votes: List[Vote], remaining: Set[str]) -> Counter:
            counter = Counter()
            for vote in votes:
                sorted_rankings = sorted(
                    [(k, v) for k, v in vote.rankings.items() if k in remaining],
                    key=lambda x: x[1],
                )
                if sorted_rankings:
                    counter[sorted_rankings[0][0]] += 1
            return counter
        
        # IRV rounds
        while len(remaining) > 1:
            counter = count_first_choices(votes, remaining)
            rounds.append(dict(counter))
            
            total = sum(counter.values())
            
            # Check for majority
            for opt_id, count in counter.items():
                if count > total / 2:
                    results.winner = opt_id
                    break
            
            if results.winner:
                break
            
            # Eliminate lowest
            if counter:
                lowest = counter.most_common()[-1][0]
                remaining.remove(lowest)
        
        # Set winner if not found
        if not results.winner and remaining:
            results.winner = list(remaining)[0]
        
        if results.winner:
            for opt in poll.options:
                if opt.id == results.winner:
                    results.winner_label = opt.label
                    break
        
        results.instant_runoff_rounds = rounds
        
        # Final counts
        if rounds:
            results.option_counts = rounds[-1]
    
    def _calculate_score_results(
        self,
        poll: Poll,
        votes: List[Vote],
        results: PollResults,
    ):
        """Calculate score-based results."""
        scores: Dict[str, List[int]] = defaultdict(list)
        
        for vote in votes:
            for opt_id, score in vote.scores.items():
                scores[opt_id].append(score)
        
        # Calculate average scores
        for opt_id, score_list in scores.items():
            results.option_scores[opt_id] = sum(score_list) / len(score_list) if score_list else 0
            results.option_counts[opt_id] = len(score_list)
        
        # Find winner
        if results.option_scores:
            winner_id = max(results.option_scores, key=results.option_scores.get)
            results.winner = winner_id
            
            for opt in poll.options:
                if opt.id == winner_id:
                    results.winner_label = opt.label
                    break
        
        results.ranked_results = sorted(
            results.option_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )
    
    async def list_polls(
        self,
        status: Optional[PollStatus] = None,
    ) -> List[Poll]:
        """List polls."""
        return await self._polls.list(status)
    
    def get_stats(self) -> VotingStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_voting_system() -> VotingSystem:
    """Create voting system."""
    return VotingSystem()


def create_poll(
    title: str,
    **kwargs,
) -> Poll:
    """Create poll."""
    return Poll(title=title, **kwargs)


def create_poll_option(
    label: str,
    **kwargs,
) -> PollOption:
    """Create poll option."""
    return PollOption(label=label, **kwargs)


__all__ = [
    # Exceptions
    "VotingError",
    "PollNotFoundError",
    "VotingNotAllowedError",
    # Enums
    "VotingType",
    "PollStatus",
    "VoteStatus",
    # Data classes
    "PollOption",
    "Poll",
    "Vote",
    "PollResults",
    "VotingStats",
    # Stores
    "PollStore",
    "InMemoryPollStore",
    "VoteStore",
    "InMemoryVoteStore",
    # System
    "VotingSystem",
    # Factory functions
    "create_voting_system",
    "create_poll",
    "create_poll_option",
]
