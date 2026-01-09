"""
Audit Trail Manager.

Comprehensive audit trail system with:
- Event logging
- Tamper-evident storage
- Query and filtering
- Compliance reporting
- Event correlation
"""

import uuid
import time
import logging
import json
import hashlib
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from collections import defaultdict

from .types import AuditEventType, AuditSeverity, AuditEvent

logger = logging.getLogger(__name__)


class AuditTrailManager:
    """
    Comprehensive audit trail system.
    
    Features:
    - Event logging
    - Tamper-evident storage
    - Query and filtering
    - Compliance reporting
    - Event correlation
    """
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path
        self.events: List[AuditEvent] = []
        self._lock = threading.Lock()
        self._handlers: List[Callable[[AuditEvent], None]] = []
        self._event_index: Dict[str, List[int]] = defaultdict(list)
        
        # Chain for integrity verification
        self._chain_hash = "genesis"
    
    def log(self,
           event_type: AuditEventType,
           actor: str,
           resource: str,
           action: str,
           details: Dict[str, Any] = None,
           outcome: str = "success",
           severity: AuditSeverity = AuditSeverity.INFO,
           ip_address: str = None,
           user_agent: str = None,
           tenant_id: str = None,
           correlation_id: str = None,
           metadata: Dict[str, Any] = None) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            actor: Who performed the action
            resource: What was affected
            action: What was done
            details: Additional details
            outcome: success, failure, denied
            severity: Event severity
            ip_address: Client IP
            user_agent: Client user agent
            tenant_id: Tenant identifier
            correlation_id: For tracking related events
            metadata: Additional metadata
            
        Returns:
            Created audit event
        """
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            timestamp=time.time(),
            actor=actor,
            resource=resource,
            action=action,
            details=details or {},
            outcome=outcome,
            ip_address=ip_address,
            user_agent=user_agent,
            tenant_id=tenant_id,
            correlation_id=correlation_id or str(uuid.uuid4()),
            metadata=metadata or {}
        )
        
        with self._lock:
            # Update chain hash for integrity
            event.metadata['chain_hash'] = self._update_chain(event)
            
            # Store event
            idx = len(self.events)
            self.events.append(event)
            
            # Update indexes
            self._event_index[f"type:{event_type.value}"].append(idx)
            self._event_index[f"actor:{actor}"].append(idx)
            self._event_index[f"resource:{resource}"].append(idx)
            self._event_index[f"correlation:{event.correlation_id}"].append(idx)
            if tenant_id:
                self._event_index[f"tenant:{tenant_id}"].append(idx)
        
        # Call handlers
        for handler in self._handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Audit handler error: %s", e)
        
        logger.debug("Audit: %s %s %s -> %s", event_type.value, actor, action, outcome)
        return event
    
    def _update_chain(self, event: AuditEvent) -> str:
        """Update blockchain-like chain for integrity."""
        event_data = json.dumps(event.to_dict(), sort_keys=True)
        combined = f"{self._chain_hash}{event_data}"
        self._chain_hash = hashlib.sha256(combined.encode()).hexdigest()
        return self._chain_hash
    
    def verify_integrity(self) -> Dict[str, Any]:
        """Verify audit trail integrity."""
        result = {
            'valid': True,
            'events_checked': 0,
            'errors': []
        }
        
        chain_hash = "genesis"
        
        for i, event in enumerate(self.events):
            # Recalculate hash
            event_data = event.to_dict()
            stored_hash = event_data.get('metadata', {}).get('chain_hash')
            event_data['metadata'] = {k: v for k, v in event_data.get('metadata', {}).items() 
                                     if k != 'chain_hash'}
            
            combined = f"{chain_hash}{json.dumps(event_data, sort_keys=True)}"
            expected_hash = hashlib.sha256(combined.encode()).hexdigest()
            
            if stored_hash != expected_hash:
                result['valid'] = False
                result['errors'].append({
                    'index': i,
                    'event_id': event.event_id,
                    'error': 'Hash mismatch - possible tampering'
                })
            
            chain_hash = stored_hash or expected_hash
            result['events_checked'] += 1
        
        return result
    
    def query(self,
             event_type: AuditEventType = None,
             actor: str = None,
             resource: str = None,
             start_time: float = None,
             end_time: float = None,
             tenant_id: str = None,
             correlation_id: str = None,
             severity: AuditSeverity = None,
             outcome: str = None,
             limit: int = 100) -> List[AuditEvent]:
        """
        Query audit events.
        
        Args:
            Various filters...
            limit: Maximum events to return
            
        Returns:
            List of matching events
        """
        # Start with indexed results if possible
        candidate_indices = None
        
        if correlation_id:
            candidate_indices = set(self._event_index[f"correlation:{correlation_id}"])
        elif tenant_id:
            candidate_indices = set(self._event_index[f"tenant:{tenant_id}"])
        elif actor:
            candidate_indices = set(self._event_index[f"actor:{actor}"])
        elif event_type:
            candidate_indices = set(self._event_index[f"type:{event_type.value}"])
        
        # Filter events
        results = []
        events = [self.events[i] for i in candidate_indices] if candidate_indices else self.events
        
        for event in events:
            if event_type and event.event_type != event_type:
                continue
            if actor and event.actor != actor:
                continue
            if resource and not event.resource.startswith(resource):
                continue
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            if tenant_id and event.tenant_id != tenant_id:
                continue
            if severity and event.severity != severity:
                continue
            if outcome and event.outcome != outcome:
                continue
            
            results.append(event)
            if len(results) >= limit:
                break
        
        return results
    
    def add_handler(self, handler: Callable[[AuditEvent], None]):
        """Add event handler."""
        self._handlers.append(handler)
    
    def generate_report(self,
                       start_time: float,
                       end_time: float,
                       tenant_id: str = None) -> Dict[str, Any]:
        """Generate compliance report."""
        events = self.query(
            start_time=start_time,
            end_time=end_time,
            tenant_id=tenant_id,
            limit=10000
        )
        
        report = {
            'report_id': str(uuid.uuid4()),
            'generated_at': time.time(),
            'period': {
                'start': datetime.fromtimestamp(start_time).isoformat(),
                'end': datetime.fromtimestamp(end_time).isoformat()
            },
            'tenant_id': tenant_id,
            'total_events': len(events),
            'by_type': defaultdict(int),
            'by_outcome': defaultdict(int),
            'by_severity': defaultdict(int),
            'by_actor': defaultdict(int),
            'security_events': [],
            'failed_actions': [],
            'integrity_check': self.verify_integrity()
        }
        
        for event in events:
            report['by_type'][event.event_type.value] += 1
            report['by_outcome'][event.outcome] += 1
            report['by_severity'][event.severity.value] += 1
            report['by_actor'][event.actor] += 1
            
            if event.event_type == AuditEventType.SECURITY_EVENT:
                report['security_events'].append(event.to_dict())
            
            if event.outcome in ['failure', 'denied']:
                report['failed_actions'].append(event.to_dict())
        
        # Convert defaultdicts
        report['by_type'] = dict(report['by_type'])
        report['by_outcome'] = dict(report['by_outcome'])
        report['by_severity'] = dict(report['by_severity'])
        report['by_actor'] = dict(report['by_actor'])
        
        return report
    
    def export(self, filepath: str, output_format: str = "json"):
        """Export audit trail."""
        events_data = [e.to_dict() for e in self.events]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            if output_format == "json":
                json.dump(events_data, f, indent=2)
            elif output_format == "jsonl":
                for event in events_data:
                    f.write(json.dumps(event) + '\n')
        
        logger.info("Exported %d audit events to %s", len(events_data), filepath)


__all__ = ['AuditTrailManager']
