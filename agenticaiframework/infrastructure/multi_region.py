"""
Multi-Region Manager.

Manages multi-region deployment and routing with:
- Geographic load balancing
- Failover handling
- Latency-based routing
- Region health monitoring
"""

import logging
import threading
import random
from typing import Dict, Any, Optional
from collections import defaultdict

from .types import Region, RegionConfig

logger = logging.getLogger(__name__)


class MultiRegionManager:
    """
    Manages multi-region deployment and routing.
    
    Features:
    - Geographic load balancing
    - Failover handling
    - Latency-based routing
    - Region health monitoring
    """
    
    def __init__(self):
        self.regions: Dict[Region, RegionConfig] = {}
        self.primary_region: Optional[Region] = None
        self.routing_mode: str = "latency"  # latency, round-robin, weighted
        self._health_check_interval: int = 30
        self._lock = threading.Lock()
        self._request_counts: Dict[Region, int] = defaultdict(int)
    
    def register_region(self, config: RegionConfig):
        """Register a region."""
        with self._lock:
            self.regions[config.region] = config
            
            if config.is_primary:
                self.primary_region = config.region
        
        logger.info("Registered region: %s (primary: %s)", 
                   config.region.value, config.is_primary)
    
    def set_routing_mode(self, mode: str):
        """Set routing mode."""
        if mode not in ["latency", "round-robin", "weighted", "primary-only"]:
            raise ValueError(f"Invalid routing mode: {mode}")
        self.routing_mode = mode
        logger.info("Set routing mode to: %s", mode)
    
    def get_region(self, user_region: Region = None) -> Region:
        """
        Get the best region for a request.
        
        Args:
            user_region: User's geographic region (for latency routing)
        """
        healthy_regions = [
            r for r, c in self.regions.items() 
            if c.health_status == "healthy"
        ]
        
        if not healthy_regions:
            raise RuntimeError("No healthy regions available")
        
        if self.routing_mode == "primary-only":
            if self.primary_region and self.primary_region in healthy_regions:
                return self.primary_region
            return healthy_regions[0]
        
        if self.routing_mode == "round-robin":
            region = min(healthy_regions, key=lambda r: self._request_counts[r])
            self._request_counts[region] += 1
            return region
        
        if self.routing_mode == "weighted":
            weights = [self.regions[r].weight for r in healthy_regions]
            return random.choices(healthy_regions, weights=weights)[0]
        
        # Latency-based (default)
        if user_region and user_region in healthy_regions:
            return user_region
        
        # Return region with lowest latency
        return min(healthy_regions, key=lambda r: self.regions[r].latency_ms)
    
    def update_health(self, region: Region, status: str, latency_ms: float = None):
        """Update region health status."""
        if region not in self.regions:
            return
        
        with self._lock:
            self.regions[region].health_status = status
            if latency_ms is not None:
                self.regions[region].latency_ms = latency_ms
        
        logger.info("Updated region %s health: %s (latency: %s ms)",
                   region.value, status, latency_ms)
    
    def failover(self, failed_region: Region) -> Region:
        """Handle region failover."""
        self.update_health(failed_region, "unhealthy")
        
        # Get next best region
        new_region = self.get_region()
        
        logger.warning("Failover from %s to %s", 
                      failed_region.value, new_region.value)
        
        return new_region
    
    def get_status(self) -> Dict[str, Any]:
        """Get multi-region status."""
        return {
            'routing_mode': self.routing_mode,
            'primary_region': self.primary_region.value if self.primary_region else None,
            'regions': {
                r.value: {
                    'endpoint': c.endpoint,
                    'is_primary': c.is_primary,
                    'health_status': c.health_status,
                    'latency_ms': c.latency_ms,
                    'weight': c.weight,
                    'request_count': self._request_counts[r]
                }
                for r, c in self.regions.items()
            }
        }


__all__ = ['MultiRegionManager']
