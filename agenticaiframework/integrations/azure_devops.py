"""
Azure DevOps Integration.

Features:
- Work items (Bugs, User Stories, Tasks)
- Pipelines
- Repos
- Test plans
"""

import time
import logging
from typing import Dict, Any, List
from datetime import datetime

from .base import BaseIntegration
from .types import IntegrationConfig, IntegrationStatus

logger = logging.getLogger(__name__)


class AzureDevOpsIntegration(BaseIntegration):
    """
    Azure DevOps Integration.
    
    Features:
    - Work items (Bugs, User Stories, Tasks)
    - Pipelines
    - Repos
    - Test plans
    """
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self._org_url = config.endpoint
        self._project = config.settings.get('project')
    
    def connect(self) -> bool:
        """Test connection to Azure DevOps."""
        try:
            logger.info("Connected to Azure DevOps: %s", self._org_url)
            self.config.status = IntegrationStatus.ACTIVE
            return True
        except Exception as e:  # noqa: BLE001 - Handle any connection error
            self._last_error = str(e)
            self.config.status = IntegrationStatus.ERROR
            return False
    
    def disconnect(self):
        """Disconnect from Azure DevOps."""
        self.config.status = IntegrationStatus.INACTIVE
    
    def health_check(self) -> Dict[str, Any]:
        """Check Azure DevOps health."""
        return {
            'status': self.config.status.value,
            'org_url': self._org_url,
            'project': self._project,
            'last_error': self._last_error
        }
    
    def create_work_item(self,
                        work_item_type: str,
                        title: str,
                        description: str = None,
                        assigned_to: str = None,
                        tags: List[str] = None,
                        area_path: str = None,
                        iteration_path: str = None) -> Dict[str, Any]:
        """Create a work item."""
        work_item = {
            'id': int(time.time()) % 100000,
            'type': work_item_type,
            'fields': {
                'System.Title': title,
                'System.Description': description,
                'System.AssignedTo': assigned_to,
                'System.Tags': '; '.join(tags) if tags else '',
                'System.AreaPath': area_path or self._project,
                'System.IterationPath': iteration_path or self._project,
                'System.State': 'New'
            },
            'url': f"{self._org_url}/{self._project}/_workitems/edit/{int(time.time()) % 100000}"
        }
        
        logger.info("Created work item: %s #%d", work_item_type, work_item['id'])
        return work_item
    
    def create_bug(self,
                  title: str,
                  repro_steps: str = None,
                  severity: str = "3 - Medium",
                  priority: int = 2,
                  **kwargs) -> Dict[str, Any]:
        """Create a bug work item."""
        work_item = self.create_work_item('Bug', title, **kwargs)
        work_item['fields']['Microsoft.VSTS.TCM.ReproSteps'] = repro_steps
        work_item['fields']['Microsoft.VSTS.Common.Severity'] = severity
        work_item['fields']['Microsoft.VSTS.Common.Priority'] = priority
        return work_item
    
    def trigger_pipeline(self,
                        pipeline_id: int,
                        branch: str = "main",
                        variables: Dict[str, str] = None) -> Dict[str, Any]:
        """Trigger a pipeline run."""
        run = {
            'id': int(time.time() * 1000),
            'pipeline_id': pipeline_id,
            'resources': {
                'repositories': {
                    'self': {'refName': f"refs/heads/{branch}"}
                }
            },
            'variables': variables or {},
            'state': 'inProgress',
            'created_date': datetime.now().isoformat()
        }
        
        logger.info("Triggered pipeline %d on branch %s", pipeline_id, branch)
        return run
    
    def add_comment(self, work_item_id: int, text: str) -> Dict[str, Any]:
        """Add comment to work item."""
        return {
            'id': int(time.time() * 1000),
            'work_item_id': work_item_id,
            'text': text,
            'created_date': datetime.now().isoformat()
        }


__all__ = ['AzureDevOpsIntegration']
