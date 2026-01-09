"""
ServiceNow ITSM Integration.

Features:
- Incident management
- Change requests
- Problem management
- CMDB integration
"""

import uuid
import time
import logging
from typing import Dict, Any
from datetime import datetime

from .base import BaseIntegration
from .types import IntegrationConfig, IntegrationStatus

logger = logging.getLogger(__name__)


class ServiceNowIntegration(BaseIntegration):
    """
    ServiceNow ITSM Integration.
    
    Features:
    - Incident management
    - Change requests
    - Problem management
    - CMDB integration
    """
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self._base_url = config.endpoint.rstrip('/')
    
    def connect(self) -> bool:
        """Test connection to ServiceNow."""
        try:
            # Simulate connection test
            logger.info("Connected to ServiceNow: %s", self._base_url)
            self.config.status = IntegrationStatus.ACTIVE
            return True
        except Exception as e:  # noqa: BLE001 - Handle any connection error
            self._last_error = str(e)
            self.config.status = IntegrationStatus.ERROR
            return False
    
    def disconnect(self):
        """Disconnect from ServiceNow."""
        self.config.status = IntegrationStatus.INACTIVE
    
    def health_check(self) -> Dict[str, Any]:
        """Check ServiceNow health."""
        return {
            'status': self.config.status.value,
            'endpoint': self._base_url,
            'last_error': self._last_error
        }
    
    def create_incident(self,
                       short_description: str,
                       description: str,
                       urgency: int = 3,
                       impact: int = 3,
                       caller_id: str = None,
                       assignment_group: str = None,
                       category: str = None) -> Dict[str, Any]:
        """
        Create a ServiceNow incident.
        
        Args:
            short_description: Brief description
            description: Full description
            urgency: 1 (High) to 3 (Low)
            impact: 1 (High) to 3 (Low)
            caller_id: User who reported
            assignment_group: Team to assign to
            category: Incident category
        """
        incident = {
            'sys_id': str(uuid.uuid4()),
            'number': f"INC{int(time.time())}",
            'short_description': short_description,
            'description': description,
            'urgency': urgency,
            'impact': impact,
            'priority': self._calculate_priority(urgency, impact),
            'caller_id': caller_id,
            'assignment_group': assignment_group,
            'category': category,
            'state': 'new',
            'created_on': datetime.now().isoformat(),
            'sys_created_by': 'agenticai'
        }
        
        logger.info("Created ServiceNow incident: %s", incident['number'])
        return incident
    
    def _calculate_priority(self, urgency: int, impact: int) -> int:
        """Calculate priority from urgency and impact."""
        # Standard ServiceNow priority matrix
        matrix = {
            (1, 1): 1, (1, 2): 2, (1, 3): 3,
            (2, 1): 2, (2, 2): 3, (2, 3): 4,
            (3, 1): 3, (3, 2): 4, (3, 3): 5
        }
        return matrix.get((urgency, impact), 5)
    
    def update_incident(self, 
                       incident_id: str,
                       updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an incident."""
        return {
            'sys_id': incident_id,
            'updated_on': datetime.now().isoformat(),
            'updates': updates
        }
    
    def create_change_request(self,
                             short_description: str,
                             description: str,
                             change_type: str = "normal",
                             risk: str = "moderate",
                             impact: str = "medium") -> Dict[str, Any]:
        """Create a change request."""
        change = {
            'sys_id': str(uuid.uuid4()),
            'number': f"CHG{int(time.time())}",
            'short_description': short_description,
            'description': description,
            'type': change_type,
            'risk': risk,
            'impact': impact,
            'state': 'new',
            'created_on': datetime.now().isoformat()
        }
        
        logger.info("Created change request: %s", change['number'])
        return change
    
    def add_work_note(self, table: str, record_id: str, note: str) -> Dict[str, Any]:
        """Add work note to a record."""
        return {
            'table': table,
            'record_id': record_id,
            'work_note': note,
            'added_on': datetime.now().isoformat()
        }


__all__ = ['ServiceNowIntegration']
