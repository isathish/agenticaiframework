"""
Tests for security rate limiting module.
"""

import time
import pytest
from unittest.mock import Mock, patch

from agenticaiframework.security.rate_limiting import RateLimiter, TieredRateLimiter


class TestRateLimiter:
    """Tests for RateLimiter class."""
    
    def test_init_default(self):
        """Test default initialization."""
        limiter = RateLimiter()
        assert limiter.max_requests == 100
        assert limiter.time_window == 60
    
    def test_init_custom(self):
        """Test custom initialization."""
        limiter = RateLimiter(max_requests=10, time_window=30)
        assert limiter.max_requests == 10
        assert limiter.time_window == 30
    
    def test_is_allowed_first_request(self):
        """Test first request is always allowed."""
        limiter = RateLimiter(max_requests=5)
        
        assert limiter.is_allowed("user1") is True
    
    def test_is_allowed_under_limit(self):
        """Test requests under limit are allowed."""
        limiter = RateLimiter(max_requests=5)
        
        for i in range(3):
            assert limiter.is_allowed("user1") is True
    
    def test_is_allowed_at_limit(self):
        """Test request at limit is blocked."""
        limiter = RateLimiter(max_requests=3)
        
        # First 3 allowed
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        
        # 4th blocked
        assert limiter.is_allowed("user1") is False
    
    def test_is_allowed_multiple_users(self):
        """Test rate limiting is per user."""
        limiter = RateLimiter(max_requests=2)
        
        # User 1 uses both requests
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is False
        
        # User 2 still has full allowance
        assert limiter.is_allowed("user2") is True
        assert limiter.is_allowed("user2") is True
    
    def test_get_remaining_requests(self):
        """Test getting remaining request count."""
        limiter = RateLimiter(max_requests=5)
        
        assert limiter.get_remaining_requests("user1") == 5
        
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        
        assert limiter.get_remaining_requests("user1") == 3
    
    def test_get_remaining_requests_unknown_user(self):
        """Test remaining requests for unknown user."""
        limiter = RateLimiter(max_requests=5)
        
        assert limiter.get_remaining_requests("unknown") == 5
    
    def test_reset_single_user(self):
        """Test resetting rate limit for single user."""
        limiter = RateLimiter(max_requests=2)
        
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        assert limiter.is_allowed("user1") is False
        
        limiter.reset("user1")
        
        assert limiter.is_allowed("user1") is True
    
    def test_reset_all(self):
        """Test resetting all rate limits."""
        limiter = RateLimiter(max_requests=2)
        
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        limiter.is_allowed("user2")
        limiter.is_allowed("user2")
        
        limiter.reset()
        
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user2") is True
    
    def test_update_limits(self):
        """Test updating rate limits."""
        limiter = RateLimiter(max_requests=5, time_window=60)
        
        limiter.update_limits(max_requests=10, time_window=120)
        
        assert limiter.max_requests == 10
        assert limiter.time_window == 120
    
    def test_update_limits_partial(self):
        """Test partial update of rate limits."""
        limiter = RateLimiter(max_requests=5, time_window=60)
        
        limiter.update_limits(max_requests=10)
        
        assert limiter.max_requests == 10
        assert limiter.time_window == 60
    
    def test_get_wait_time_no_limit(self):
        """Test wait time when not rate limited."""
        limiter = RateLimiter(max_requests=5)
        
        wait_time = limiter.get_wait_time("user1")
        assert wait_time == 0.0
    
    def test_window_expiration(self):
        """Test that requests expire outside window."""
        limiter = RateLimiter(max_requests=2, time_window=1)
        
        # Use both requests
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        assert limiter.is_allowed("user1") is False
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should be allowed again
        assert limiter.is_allowed("user1") is True


class TestTieredRateLimiter:
    """Tests for TieredRateLimiter class."""
    
    def test_init(self):
        """Test TieredRateLimiter initialization."""
        limiter = TieredRateLimiter()
        assert limiter is not None
    
    def test_has_tiers(self):
        """Test that limiter has tier support."""
        limiter = TieredRateLimiter()
        assert hasattr(limiter, 'tiers') or hasattr(limiter, 'get_tier_limits')


class TestRateLimiterEdgeCases:
    """Edge case tests for RateLimiter."""
    
    def test_zero_max_requests(self):
        """Test with zero max requests."""
        limiter = RateLimiter(max_requests=0)
        
        # No requests should be allowed
        assert limiter.is_allowed("user1") is False
    
    def test_large_request_count(self):
        """Test with large number of requests."""
        limiter = RateLimiter(max_requests=10000)
        
        # Make many requests
        for _ in range(1000):
            assert limiter.is_allowed("user1") is True
    
    def test_empty_identifier(self):
        """Test with empty identifier."""
        limiter = RateLimiter(max_requests=5)
        
        assert limiter.is_allowed("") is True
    
    def test_special_characters_identifier(self):
        """Test with special characters in identifier."""
        limiter = RateLimiter(max_requests=5)
        
        assert limiter.is_allowed("user@example.com") is True
        assert limiter.is_allowed("192.168.1.1") is True
        assert limiter.is_allowed("user:123:session") is True
