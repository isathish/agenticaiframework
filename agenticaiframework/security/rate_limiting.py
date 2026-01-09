"""
Rate Limiting for abuse prevention.

Provides rate limiting functionality to prevent API abuse.
"""

import time
import logging
from typing import Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiting to prevent abuse."""
    
    def __init__(self, max_requests: int = 100, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, List[float]] = defaultdict(list)
        
    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed for the given identifier.
        
        Args:
            identifier: Unique identifier (e.g., user_id, IP address)
            
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        current_time = time.time()
        cutoff_time = current_time - self.time_window
        
        # Remove old requests outside the time window
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > cutoff_time
        ]
        
        # Check if limit exceeded
        if len(self.requests[identifier]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[identifier].append(current_time)
        return True
    
    def get_remaining_requests(self, identifier: str) -> int:
        """Get the number of remaining requests for identifier."""
        current_time = time.time()
        cutoff_time = current_time - self.time_window
        
        # Count valid requests
        valid_requests = [
            req_time for req_time in self.requests.get(identifier, [])
            if req_time > cutoff_time
        ]
        
        return max(0, self.max_requests - len(valid_requests))
    
    def get_wait_time(self, identifier: str) -> float:
        """Get time in seconds until a request is allowed."""
        if self.is_allowed(identifier):
            # Pop the request we just added for checking
            self.requests[identifier].pop()
            return 0.0
        
        if not self.requests[identifier]:
            return 0.0
        
        # Find oldest request in window
        oldest_request = min(self.requests[identifier])
        wait_time = (oldest_request + self.time_window) - time.time()
        return max(0.0, wait_time)
    
    def reset(self, identifier: str = None):
        """Reset rate limit for identifier or all identifiers."""
        if identifier:
            self.requests.pop(identifier, None)
        else:
            self.requests.clear()
    
    def update_limits(self, max_requests: int = None, time_window: int = None):
        """Update rate limiting parameters."""
        if max_requests is not None:
            self.max_requests = max_requests
        if time_window is not None:
            self.time_window = time_window


class TieredRateLimiter:
    """Rate limiter with different tiers for different user types."""
    
    DEFAULT_TIERS = {
        'free': {'max_requests': 60, 'time_window': 60},
        'basic': {'max_requests': 300, 'time_window': 60},
        'premium': {'max_requests': 1000, 'time_window': 60},
        'unlimited': {'max_requests': 1000000, 'time_window': 60},
    }
    
    def __init__(self, tiers: Dict[str, Dict] = None):
        """
        Initialize tiered rate limiter.
        
        Args:
            tiers: Dictionary of tier names to rate limit configs
        """
        self.tiers = tiers or self.DEFAULT_TIERS
        self.limiters: Dict[str, RateLimiter] = {}
        self.user_tiers: Dict[str, str] = {}
        
        # Create rate limiters for each tier
        for tier_name, config in self.tiers.items():
            self.limiters[tier_name] = RateLimiter(
                max_requests=config['max_requests'],
                time_window=config['time_window']
            )
    
    def set_user_tier(self, user_id: str, tier: str):
        """Set the tier for a user."""
        if tier not in self.tiers:
            raise ValueError(f"Unknown tier: {tier}")
        self.user_tiers[user_id] = tier
    
    def get_user_tier(self, user_id: str) -> str:
        """Get the tier for a user, defaulting to 'free'."""
        return self.user_tiers.get(user_id, 'free')
    
    def is_allowed(self, user_id: str) -> bool:
        """Check if request is allowed for user based on their tier."""
        tier = self.get_user_tier(user_id)
        return self.limiters[tier].is_allowed(user_id)
    
    def get_remaining_requests(self, user_id: str) -> int:
        """Get remaining requests for user based on their tier."""
        tier = self.get_user_tier(user_id)
        return self.limiters[tier].get_remaining_requests(user_id)
