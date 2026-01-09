"""
Distributed Coordinator.

Coordinates distributed agent execution with:
- Distributed locking
- Leader election
- Task distribution
- Consensus
"""

import uuid
import time
import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DistributedCoordinator:
    """
    Coordinates distributed agent execution.
    
    Features:
    - Distributed locking
    - Leader election
    - Task distribution
    - Consensus
    """
    
    def __init__(self, node_id: str = None):
        self.node_id = node_id or str(uuid.uuid4())
        self.locks: Dict[str, Dict[str, Any]] = {}
        self.leader: Optional[str] = None
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        
        # Register self
        self._register_node()
    
    def _register_node(self):
        """Register this node."""
        self.nodes[self.node_id] = {
            'node_id': self.node_id,
            'registered_at': time.time(),
            'last_heartbeat': time.time(),
            'status': 'active'
        }
    
    def acquire_lock(self, 
                    lock_name: str,
                    timeout_seconds: float = 30) -> bool:
        """
        Acquire a distributed lock.
        
        Args:
            lock_name: Name of lock
            timeout_seconds: Lock timeout
        """
        with self._lock:
            if lock_name in self.locks:
                existing = self.locks[lock_name]
                
                # Check if lock expired
                if time.time() - existing['acquired_at'] > existing['timeout']:
                    pass  # Lock expired, can acquire
                elif existing['owner'] == self.node_id:
                    # Reentrant
                    existing['count'] += 1
                    return True
                else:
                    return False
            
            self.locks[lock_name] = {
                'owner': self.node_id,
                'acquired_at': time.time(),
                'timeout': timeout_seconds,
                'count': 1
            }
        
        logger.debug("Node %s acquired lock '%s'", self.node_id, lock_name)
        return True
    
    def release_lock(self, lock_name: str) -> bool:
        """Release a distributed lock."""
        with self._lock:
            if lock_name not in self.locks:
                return False
            
            lock = self.locks[lock_name]
            if lock['owner'] != self.node_id:
                return False
            
            lock['count'] -= 1
            if lock['count'] <= 0:
                del self.locks[lock_name]
        
        logger.debug("Node %s released lock '%s'", self.node_id, lock_name)
        return True
    
    def elect_leader(self) -> str:
        """Perform leader election."""
        active_nodes = [
            nid for nid, info in self.nodes.items()
            if info['status'] == 'active' and 
            time.time() - info['last_heartbeat'] < 60
        ]
        
        if not active_nodes:
            self.leader = self.node_id
        else:
            # Simple: lowest node ID wins
            self.leader = min(active_nodes)
        
        logger.info("Leader elected: %s", self.leader)
        return self.leader
    
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self.leader == self.node_id
    
    def submit_task(self, 
                   task_id: str,
                   task_data: Any,
                   target_node: str = None) -> Dict[str, Any]:
        """Submit a task for distributed execution."""
        if target_node is None:
            # Round-robin distribution
            active_nodes = [
                nid for nid, info in self.nodes.items()
                if info['status'] == 'active'
            ]
            if not active_nodes:
                target_node = self.node_id
            else:
                target_node = active_nodes[len(self.tasks) % len(active_nodes)]
        
        task = {
            'task_id': task_id,
            'data': task_data,
            'target_node': target_node,
            'submitted_by': self.node_id,
            'submitted_at': time.time(),
            'status': 'pending'
        }
        
        self.tasks[task_id] = task
        logger.info("Submitted task %s to node %s", task_id, target_node)
        
        return task
    
    def heartbeat(self):
        """Send heartbeat."""
        if self.node_id in self.nodes:
            self.nodes[self.node_id]['last_heartbeat'] = time.time()
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """Get cluster status."""
        active_count = sum(
            1 for info in self.nodes.values()
            if info['status'] == 'active' and 
            time.time() - info['last_heartbeat'] < 60
        )
        
        return {
            'node_id': self.node_id,
            'is_leader': self.is_leader(),
            'leader': self.leader,
            'total_nodes': len(self.nodes),
            'active_nodes': active_count,
            'active_locks': len(self.locks),
            'pending_tasks': sum(
                1 for t in self.tasks.values() if t['status'] == 'pending'
            )
        }


__all__ = ['DistributedCoordinator']
