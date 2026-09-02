"""
Azure DevOps Integration (REST API 7.1).

Features:
- Work items (Bugs, User Stories, Tasks)
- Pipelines
- Repos
- Test plans

Authentication: ``auth_type="basic"`` with ``credentials["password"]`` = a PAT
(username may be blank), or ``auth_type="oauth"`` with an AAD access token.
``config.endpoint`` is the organisation URL, e.g. ``https://dev.azure.com/acme``.
"""

import logging
from typing import Dict, Any, List, Optional
from urllib.parse import quote

from .base import BaseIntegration
from .types import IntegrationConfig, IntegrationStatus

logger = logging.getLogger(__name__)

_API = '7.1'


class AzureDevOpsIntegration(BaseIntegration):
    """Azure DevOps REST integration."""
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self._org_url = config.endpoint.rstrip('/')
        self._project = config.settings.get('project')
        self._api_version = config.settings.get('api_version', _API)
    
    def _url(self, path: str, project: bool = True, **params: Any) -> str:
        from urllib.parse import urlencode
        base = self._org_url
        if project:
            if not self._project:
                raise ValueError("Azure DevOps integration requires settings['project']")
            base = f"{base}/{quote(self._project)}"
        query = {'api-version': self._api_version, **{k: v for k, v in params.items() if v is not None}}
        return f"{base}/_apis/{path.lstrip('/')}?{urlencode(query)}"
    
    def connect(self) -> bool:
        """Test connection by listing projects."""
        try:
            data = self._request('GET', self._url('projects', project=False, **{'$top': 1}))
            self.config.metadata['project_count'] = data.get('count')
            logger.info("Connected to Azure DevOps: %s", self._org_url)
            self.config.status = IntegrationStatus.ACTIVE
            self._last_error = None
            return True
        except Exception as e:  # noqa: BLE001 - surface any connection error via status
            self._last_error = str(e)
            self.config.status = IntegrationStatus.ERROR
            return False
    
    def disconnect(self):
        """Disconnect from Azure DevOps."""
        self._session = None
        self.config.status = IntegrationStatus.INACTIVE
    
    def health_check(self) -> Dict[str, Any]:
        """Check Azure DevOps health."""
        result = {
            'status': self.config.status.value,
            'org_url': self._org_url,
            'project': self._project,
            'last_error': self._last_error,
        }
        try:
            self._request('GET', self._url('projects', project=False, **{'$top': 1}))
            result['reachable'] = True
        except Exception as e:  # noqa: BLE001
            result['reachable'] = False
            result['error'] = str(e)
        return result
    
    # -- work items --------------------------------------------------------------
    
    @staticmethod
    def _patch_ops(fields: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{'op': 'add', 'path': f'/fields/{k}', 'value': v} for k, v in fields.items() if v is not None]
    
    def create_work_item(self,
                        work_item_type: str,
                        title: str,
                        description: Optional[str] = None,
                        assigned_to: Optional[str] = None,
                        tags: Optional[List[str]] = None,
                        area_path: Optional[str] = None,
                        iteration_path: Optional[str] = None,
                        extra_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a work item via JSON Patch."""
        fields: Dict[str, Any] = {
            'System.Title': title,
            'System.Description': description,
            'System.AssignedTo': assigned_to,
            'System.Tags': '; '.join(tags) if tags else None,
            'System.AreaPath': area_path,
            'System.IterationPath': iteration_path,
        }
        if extra_fields:
            fields.update(extra_fields)
        url = self._url(f'wit/workitems/${quote(work_item_type)}')
        work_item = self._request('POST', url, data=__import__('json').dumps(self._patch_ops(fields)).encode(),
                                  headers={'Content-Type': 'application/json-patch+json'})
        logger.info("Created work item: %s #%s", work_item_type, work_item.get('id'))
        return work_item
    
    def create_bug(self,
                  title: str,
                  repro_steps: Optional[str] = None,
                  severity: str = "3 - Medium",
                  priority: int = 2,
                  **kwargs) -> Dict[str, Any]:
        """Create a bug work item."""
        extra = dict(kwargs.pop('extra_fields', {}) or {})
        extra.update({
            'Microsoft.VSTS.TCM.ReproSteps': repro_steps,
            'Microsoft.VSTS.Common.Severity': severity,
            'Microsoft.VSTS.Common.Priority': priority,
        })
        return self.create_work_item('Bug', title, extra_fields=extra, **kwargs)
    
    def get_work_item(self, work_item_id: int, expand: str = 'All') -> Dict[str, Any]:
        return self._request('GET', self._url(f'wit/workitems/{work_item_id}', **{'$expand': expand}))
    
    def update_work_item(self, work_item_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        import json
        return self._request('PATCH', self._url(f'wit/workitems/{work_item_id}'),
                             data=json.dumps(self._patch_ops(fields)).encode(),
                             headers={'Content-Type': 'application/json-patch+json'})
    
    def query_work_items(self, wiql: str, top: int = 200) -> List[Dict[str, Any]]:
        """Run a WIQL query and hydrate the matching work items."""
        result = self._request('POST', self._url('wit/wiql', **{'$top': top}), json={'query': wiql})
        ids = [w['id'] for w in result.get('workItems', [])][:top]
        if not ids:
            return []
        items: List[Dict[str, Any]] = []
        for i in range(0, len(ids), 200):
            chunk = ','.join(str(x) for x in ids[i:i + 200])
            data = self._request('GET', self._url('wit/workitems', ids=chunk, **{'$expand': 'Fields'}))
            items.extend(data.get('value', []))
        return items
    
    def add_comment(self, work_item_id: int, text: str) -> Dict[str, Any]:
        """Add comment to work item."""
        url = self._url(f'wit/workItems/{work_item_id}/comments')
        url = url.replace(f'api-version={self._api_version}', 'api-version=7.1-preview.4')
        return self._request('POST', url, json={'text': text})
    
    # -- pipelines -----------------------------------------------------------------
    
    def list_pipelines(self) -> List[Dict[str, Any]]:
        return self._request('GET', self._url('pipelines')).get('value', [])
    
    def trigger_pipeline(self,
                        pipeline_id: int,
                        branch: str = "main",
                        variables: Optional[Dict[str, str]] = None,
                        template_parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Trigger a pipeline run."""
        payload: Dict[str, Any] = {
            'resources': {'repositories': {'self': {'refName': f"refs/heads/{branch}"}}},
        }
        if variables:
            payload['variables'] = {k: {'value': v} for k, v in variables.items()}
        if template_parameters:
            payload['templateParameters'] = template_parameters
        run = self._request('POST', self._url(f'pipelines/{pipeline_id}/runs'), json=payload)
        logger.info("Triggered pipeline %d on branch %s -> run %s", pipeline_id, branch, run.get('id'))
        return run
    
    def get_pipeline_run(self, pipeline_id: int, run_id: int) -> Dict[str, Any]:
        return self._request('GET', self._url(f'pipelines/{pipeline_id}/runs/{run_id}'))
    
    # -- repos ---------------------------------------------------------------------
    
    def list_repositories(self) -> List[Dict[str, Any]]:
        return self._request('GET', self._url('git/repositories')).get('value', [])
    
    def create_pull_request(self, repository_id: str, source_branch: str, target_branch: str,
                            title: str, description: str = "", reviewers: Optional[List[str]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            'sourceRefName': f'refs/heads/{source_branch}',
            'targetRefName': f'refs/heads/{target_branch}',
            'title': title,
            'description': description,
        }
        if reviewers:
            payload['reviewers'] = [{'id': r} for r in reviewers]
        return self._request('POST', self._url(f'git/repositories/{quote(repository_id)}/pullrequests'), json=payload)
    
    # -- test plans ------------------------------------------------------------------
    
    def list_test_plans(self) -> List[Dict[str, Any]]:
        return self._request('GET', self._url('testplan/plans')).get('value', [])


__all__ = ['AzureDevOpsIntegration']
