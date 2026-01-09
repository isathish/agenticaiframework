"""
Canary Deployment Manager.

Manages canary deployments for AI agents:
- Progressive traffic shifting
- Health monitoring
- Automatic rollback
- Deployment gates
"""

import uuid
import time
import logging
import random
import threading
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class CanaryDeploymentManager:
    """Manages canary deployments for AI agents."""
    
    def __init__(self):
        self.deployments: Dict[str, Dict[str, Any]] = {}
        self.deployment_history: List[Dict[str, Any]] = []
        self.health_checks: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def create_deployment(self,
                         name: str,
                         baseline_version: str,
                         canary_version: str,
                         traffic_steps: List[float] = None,
                         health_threshold: float = 0.95,
                         min_samples_per_step: int = 100) -> Dict[str, Any]:
        """Create a new canary deployment."""
        if traffic_steps is None:
            traffic_steps = [0.05, 0.25, 0.50, 1.0]
        
        deployment = {
            'id': str(uuid.uuid4()),
            'name': name,
            'baseline_version': baseline_version,
            'canary_version': canary_version,
            'traffic_steps': traffic_steps,
            'current_step': 0,
            'current_traffic': traffic_steps[0],
            'health_threshold': health_threshold,
            'min_samples_per_step': min_samples_per_step,
            'status': 'active',
            'created_at': time.time(),
            'metrics': {
                'baseline': {'success': 0, 'failure': 0, 'total_latency': 0},
                'canary': {'success': 0, 'failure': 0, 'total_latency': 0}
            }
        }
        
        with self._lock:
            self.deployments[name] = deployment
        
        logger.info("Created canary deployment '%s': %s -> %s",
                   name, baseline_version, canary_version)
        return deployment
    
    def route_request(self, deployment_name: str) -> str:
        """Route a request to baseline or canary."""
        deployment = self.deployments.get(deployment_name)
        if not deployment or deployment['status'] != 'active':
            return 'baseline'
        return 'canary' if random.random() < deployment['current_traffic'] else 'baseline'
    
    def record_result(self,
                     deployment_name: str,
                     version: str,
                     success: bool,
                     latency_ms: float = 0) -> Dict[str, Any]:
        """Record a request result."""
        deployment = self.deployments.get(deployment_name)
        if not deployment:
            return {'error': 'Deployment not found'}
        
        with self._lock:
            metrics = deployment['metrics'][version]
            if success:
                metrics['success'] += 1
            else:
                metrics['failure'] += 1
            metrics['total_latency'] += latency_ms
        
        return self._evaluate_deployment(deployment_name)
    
    def _evaluate_deployment(self, deployment_name: str) -> Dict[str, Any]:
        """Evaluate deployment health and decide next action."""
        deployment = self.deployments.get(deployment_name)
        if not deployment or deployment['status'] != 'active':
            return {'action': 'none', 'reason': 'deployment not active'}
        
        canary_metrics = deployment['metrics']['canary']
        canary_total = canary_metrics['success'] + canary_metrics['failure']
        
        if canary_total < deployment['min_samples_per_step']:
            return {
                'action': 'wait',
                'reason': f'need {deployment["min_samples_per_step"] - canary_total} more samples'
            }
        
        success_rate = canary_metrics['success'] / canary_total if canary_total > 0 else 0
        
        if success_rate < deployment['health_threshold']:
            self._rollback(deployment_name, f'success rate {success_rate:.2%} below threshold')
            return {
                'action': 'rollback',
                'reason': f'success rate {success_rate:.2%} < {deployment["health_threshold"]:.2%}'
            }
        
        current_step = deployment['current_step']
        traffic_steps = deployment['traffic_steps']
        
        if current_step < len(traffic_steps) - 1:
            deployment['current_step'] += 1
            deployment['current_traffic'] = traffic_steps[deployment['current_step']]
            deployment['metrics']['canary'] = {'success': 0, 'failure': 0, 'total_latency': 0}
            
            logger.info("Advancing canary '%s' to %.0f%% traffic",
                       deployment_name, deployment['current_traffic'] * 100)
            
            return {
                'action': 'advance',
                'new_traffic': deployment['current_traffic'],
                'step': deployment['current_step']
            }
        else:
            self._complete_deployment(deployment_name)
            return {'action': 'complete', 'reason': 'all steps passed'}
    
    def _rollback(self, deployment_name: str, reason: str):
        """Rollback a deployment."""
        deployment = self.deployments.get(deployment_name)
        if deployment:
            deployment['status'] = 'rolled_back'
            deployment['rollback_reason'] = reason
            deployment['completed_at'] = time.time()
            
            self.deployment_history.append({
                'deployment': deployment.copy(),
                'outcome': 'rolled_back',
                'timestamp': time.time()
            })
            logger.warning("Rolled back canary '%s': %s", deployment_name, reason)
    
    def _complete_deployment(self, deployment_name: str):
        """Complete a successful deployment."""
        deployment = self.deployments.get(deployment_name)
        if deployment:
            deployment['status'] = 'completed'
            deployment['completed_at'] = time.time()
            
            self.deployment_history.append({
                'deployment': deployment.copy(),
                'outcome': 'completed',
                'timestamp': time.time()
            })
            logger.info("Completed canary deployment '%s'", deployment_name)
    
    def get_status(self, deployment_name: str) -> Dict[str, Any]:
        """Get deployment status and metrics."""
        deployment = self.deployments.get(deployment_name)
        if not deployment:
            return {'error': 'Deployment not found'}
        
        baseline = deployment['metrics']['baseline']
        canary = deployment['metrics']['canary']
        
        baseline_total = baseline['success'] + baseline['failure']
        canary_total = canary['success'] + canary['failure']
        
        return {
            **deployment,
            'baseline_success_rate': baseline['success'] / baseline_total if baseline_total > 0 else 0,
            'canary_success_rate': canary['success'] / canary_total if canary_total > 0 else 0,
            'baseline_avg_latency': baseline['total_latency'] / baseline_total if baseline_total > 0 else 0,
            'canary_avg_latency': canary['total_latency'] / canary_total if canary_total > 0 else 0
        }
    
    def list_deployments(self, status: str = None) -> List[Dict[str, Any]]:
        """List all deployments, optionally filtered by status."""
        deployments = list(self.deployments.values())
        if status:
            deployments = [d for d in deployments if d['status'] == status]
        return deployments
    
    def abort_deployment(self, deployment_name: str, reason: str = 'manual abort'):
        """Manually abort a deployment."""
        self._rollback(deployment_name, reason)


__all__ = ['CanaryDeploymentManager']
