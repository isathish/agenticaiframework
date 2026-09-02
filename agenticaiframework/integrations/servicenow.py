"""
ServiceNow ITSM Integration (Table API).

Features:
- Incident management
- Change requests
- Problem management
- CMDB integration

Authentication: ``auth_type="basic"`` (``credentials`` = username/password) or
``auth_type="oauth"`` (``credentials["access_token"]``). ``config.endpoint`` is the
instance URL, e.g. ``https://acme.service-now.com``.
"""

import logging
from typing import Dict, Any, List, Optional
from urllib.parse import quote

from .base import BaseIntegration
from .types import IntegrationConfig, IntegrationStatus

logger = logging.getLogger(__name__)


class ServiceNowIntegration(BaseIntegration):
    """ServiceNow Table API integration."""
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self._base_url = config.endpoint.rstrip('/')
    
    def _table_url(self, table: str, sys_id: Optional[str] = None) -> str:
        url = f"{self._base_url}/api/now/table/{quote(table)}"
        return f"{url}/{quote(sys_id)}" if sys_id else url
    
    def _get_auth_headers(self) -> Dict[str, str]:
        headers = super()._get_auth_headers()
        headers['Content-Type'] = 'application/json'
        return headers
    
    def connect(self) -> bool:
        """Test connection by reading one row from ``sys_user``."""
        try:
            self._request('GET', self._table_url('sys_user'), params={'sysparm_limit': 1, 'sysparm_fields': 'sys_id'})
            logger.info("Connected to ServiceNow: %s", self._base_url)
            self.config.status = IntegrationStatus.ACTIVE
            self._last_error = None
            return True
        except Exception as e:  # noqa: BLE001 - surface any connection error via status
            self._last_error = str(e)
            self.config.status = IntegrationStatus.ERROR
            return False
    
    def disconnect(self):
        """Disconnect from ServiceNow."""
        self._session = None
        self.config.status = IntegrationStatus.INACTIVE
    
    def health_check(self) -> Dict[str, Any]:
        """Check ServiceNow health."""
        result = {
            'status': self.config.status.value,
            'endpoint': self._base_url,
            'last_error': self._last_error,
        }
        try:
            self._request('GET', self._table_url('sys_properties'), params={'sysparm_limit': 1, 'sysparm_fields': 'sys_id'})
            result['reachable'] = True
        except Exception as e:  # noqa: BLE001
            result['reachable'] = False
            result['error'] = str(e)
        return result
    
    # -- generic table API -----------------------------------------------------
    
    def create_record(self, table: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        data = self._request('POST', self._table_url(table), json=fields)
        return data.get('result', data)
    
    def get_record(self, table: str, sys_id: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        params = {'sysparm_fields': ','.join(fields)} if fields else None
        data = self._request('GET', self._table_url(table, sys_id), params=params)
        return data.get('result', data)
    
    def update_record(self, table: str, sys_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        data = self._request('PATCH', self._table_url(table, sys_id), json=fields)
        return data.get('result', data)
    
    def delete_record(self, table: str, sys_id: str) -> bool:
        self._request('DELETE', self._table_url(table, sys_id))
        return True
    
    def query_records(self, table: str, query: str = "", fields: Optional[List[str]] = None,
                      limit: int = 100, offset: int = 0, display_value: bool = False) -> List[Dict[str, Any]]:
        """Run an encoded query (``sysparm_query``) against a table."""
        params: Dict[str, Any] = {'sysparm_limit': limit, 'sysparm_offset': offset,
                                  'sysparm_display_value': 'true' if display_value else 'false'}
        if query:
            params['sysparm_query'] = query
        if fields:
            params['sysparm_fields'] = ','.join(fields)
        data = self._request('GET', self._table_url(table), params=params)
        return data.get('result', []) if isinstance(data, dict) else []
    
    # -- incidents ---------------------------------------------------------------
    
    def create_incident(self,
                       short_description: str,
                       description: str,
                       urgency: int = 3,
                       impact: int = 3,
                       caller_id: Optional[str] = None,
                       assignment_group: Optional[str] = None,
                       category: Optional[str] = None,
                       **extra: Any) -> Dict[str, Any]:
        """
        Create a ServiceNow incident.
        
        Args:
            short_description: Brief description
            description: Full description
            urgency: 1 (High) to 3 (Low)
            impact: 1 (High) to 3 (Low)
            caller_id: User who reported (sys_id or user_name)
            assignment_group: Team to assign to (sys_id or name)
            category: Incident category
        """
        fields: Dict[str, Any] = {
            'short_description': short_description,
            'description': description,
            'urgency': str(urgency),
            'impact': str(impact),
            **extra,
        }
        if caller_id:
            fields['caller_id'] = caller_id
        if assignment_group:
            fields['assignment_group'] = assignment_group
        if category:
            fields['category'] = category
        incident = self.create_record('incident', fields)
        incident.setdefault('priority', self._calculate_priority(urgency, impact))
        logger.info("Created ServiceNow incident: %s", incident.get('number'))
        return incident
    
    def _calculate_priority(self, urgency: int, impact: int) -> int:
        """Calculate priority from urgency and impact (standard ServiceNow matrix)."""
        matrix = {
            (1, 1): 1, (1, 2): 2, (1, 3): 3,
            (2, 1): 2, (2, 2): 3, (2, 3): 4,
            (3, 1): 3, (3, 2): 4, (3, 3): 5
        }
        return matrix.get((urgency, impact), 5)
    
    def get_incident(self, incident_id: str) -> Dict[str, Any]:
        """Fetch an incident by sys_id, or by number (``INC0010001``)."""
        if incident_id.upper().startswith('INC'):
            rows = self.query_records('incident', f"number={incident_id}", limit=1)
            return rows[0] if rows else {}
        return self.get_record('incident', incident_id)
    
    def update_incident(self, 
                       incident_id: str,
                       updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an incident (sys_id or number)."""
        if incident_id.upper().startswith('INC'):
            incident_id = self.get_incident(incident_id).get('sys_id', incident_id)
        return self.update_record('incident', incident_id, updates)
    
    def resolve_incident(self, incident_id: str, close_notes: str, close_code: str = "Solved (Permanently)") -> Dict[str, Any]:
        return self.update_incident(incident_id, {'state': '6', 'close_code': close_code, 'close_notes': close_notes})
    
    # -- change / problem ---------------------------------------------------------
    
    def create_change_request(self,
                             short_description: str,
                             description: str,
                             change_type: str = "normal",
                             risk: str = "moderate",
                             impact: str = "medium",
                             **extra: Any) -> Dict[str, Any]:
        """Create a change request."""
        risk_map = {'high': '2', 'moderate': '3', 'low': '4', 'very high': '1'}
        impact_map = {'high': '1', 'medium': '2', 'low': '3'}
        fields = {
            'short_description': short_description,
            'description': description,
            'type': change_type,
            'risk': risk_map.get(risk.lower(), risk),
            'impact': impact_map.get(impact.lower(), impact),
            **extra,
        }
        change = self.create_record('change_request', fields)
        logger.info("Created change request: %s", change.get('number'))
        return change
    
    def create_problem(self, short_description: str, description: str, **extra: Any) -> Dict[str, Any]:
        problem = self.create_record('problem', {'short_description': short_description, 'description': description, **extra})
        logger.info("Created problem: %s", problem.get('number'))
        return problem
    
    def add_work_note(self, table: str, record_id: str, note: str) -> Dict[str, Any]:
        """Append a work note to a record (journal field)."""
        return self.update_record(table, record_id, {'work_notes': note})
    
    def add_comment(self, table: str, record_id: str, comment: str) -> Dict[str, Any]:
        """Append a customer-visible comment to a record."""
        return self.update_record(table, record_id, {'comments': comment})
    
    # -- CMDB ---------------------------------------------------------------------
    
    def find_ci(self, name: Optional[str] = None, ci_class: str = 'cmdb_ci', query: str = "",
                limit: int = 50) -> List[Dict[str, Any]]:
        """Look up configuration items by name or encoded query."""
        q = query or (f"nameLIKE{name}" if name else "")
        return self.query_records(ci_class, q, limit=limit)


__all__ = ['ServiceNowIntegration']
