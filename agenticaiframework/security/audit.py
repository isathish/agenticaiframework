"""
Audit Logging for security events.

Provides comprehensive audit logging functionality.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AuditLogger:
    """Audit logging for security events."""
    
    SEVERITY_LEVELS = ['debug', 'info', 'warning', 'error', 'critical']
    
    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self.logs: List[Dict[str, Any]] = []
        
    def log(self, event_type: str, details: Dict[str, Any], severity: str = 'info'):
        """
        Log a security event.
        
        Args:
            event_type: Type of event (e.g., 'access', 'injection_detected')
            details: Event details
            severity: Severity level ('debug', 'info', 'warning', 'error', 'critical')
        """
        if severity not in self.SEVERITY_LEVELS:
            severity = 'info'
            
        entry = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'severity': severity,
            'details': details
        }
        
        self.logs.append(entry)
        
        # Rotate logs if needed
        if len(self.logs) > self.max_entries:
            self.logs = self.logs[-self.max_entries:]
    
    def log_access(self, user_id: str, resource: str, action: str, success: bool = True):
        """Log an access event."""
        self.log('access', {
            'user_id': user_id,
            'resource': resource,
            'action': action,
            'success': success
        }, severity='info' if success else 'warning')
    
    def log_authentication(self, user_id: str, success: bool, method: str = 'password'):
        """Log an authentication event."""
        self.log('authentication', {
            'user_id': user_id,
            'success': success,
            'method': method
        }, severity='info' if success else 'warning')
    
    def log_security_event(self, event_type: str, user_id: str = None, details: Dict = None):
        """Log a generic security event."""
        self.log(event_type, {
            'user_id': user_id,
            **(details or {})
        }, severity='warning')
            
    def query(self, 
              event_type: str = None, 
              severity: str = None,
              start_time: datetime = None,
              end_time: datetime = None,
              user_id: str = None,
              limit: int = None) -> List[Dict[str, Any]]:
        """
        Query audit logs with filters.
        
        Args:
            event_type: Filter by event type
            severity: Filter by severity
            start_time: Filter by start time
            end_time: Filter by end time
            user_id: Filter by user ID
            limit: Maximum number of results
            
        Returns:
            Filtered list of log entries
        """
        results = self.logs
        
        if event_type:
            results = [log for log in results if log['event_type'] == event_type]
            
        if severity:
            results = [log for log in results if log['severity'] == severity]
            
        if start_time:
            results = [log for log in results 
                      if datetime.fromisoformat(log['timestamp']) >= start_time]
            
        if end_time:
            results = [log for log in results 
                      if datetime.fromisoformat(log['timestamp']) <= end_time]
            
        if user_id:
            results = [log for log in results 
                      if log.get('details', {}).get('user_id') == user_id]
        
        if limit:
            results = results[-limit:]
            
        return results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of audit logs."""
        if not self.logs:
            return {'total_entries': 0}
        
        event_types = {}
        severities = {}
        
        for log in self.logs:
            event_types[log['event_type']] = event_types.get(log['event_type'], 0) + 1
            severities[log['severity']] = severities.get(log['severity'], 0) + 1
        
        return {
            'total_entries': len(self.logs),
            'event_types': event_types,
            'severities': severities,
            'oldest_entry': self.logs[0]['timestamp'] if self.logs else None,
            'newest_entry': self.logs[-1]['timestamp'] if self.logs else None
        }
    
    def export_logs(self, filepath: str, format: str = 'json'):
        """Export logs to a file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            if format == 'json':
                json.dump(self.logs, f, indent=2)
            else:
                for log in self.logs:
                    f.write(json.dumps(log) + '\n')
            
    def clear_logs(self):
        """Clear all logs."""
        self.logs.clear()
