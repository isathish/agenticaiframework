"""
GitHub Integration (REST API v3).

Features:
- Repository management
- Issue tracking
- Pull requests
- Actions/Workflows
- Code search

Authentication: ``auth_type="api_key"`` with ``credentials["api_key"]`` set to a
personal access token / GitHub App installation token (sent as ``Bearer``), or
``auth_type="oauth"`` with ``credentials["access_token"]``.
"""

import base64
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import quote

from .base import BaseIntegration, IntegrationError
from .types import IntegrationConfig, IntegrationStatus

logger = logging.getLogger(__name__)


class GitHubIntegration(BaseIntegration):
    """GitHub REST integration."""
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self._api_url = config.settings.get('api_url', 'https://api.github.com').rstrip('/')
    
    def _get_auth_headers(self) -> Dict[str, str]:
        headers = super()._get_auth_headers()
        headers.setdefault('Accept', 'application/vnd.github+json')
        headers['X-GitHub-Api-Version'] = self.config.settings.get('api_version', '2022-11-28')
        return headers
    
    def _url(self, path: str) -> str:
        return f"{self._api_url}/{path.lstrip('/')}"
    
    def connect(self) -> bool:
        """Verify credentials against ``GET /user`` (falls back to ``/rate_limit`` for app tokens)."""
        try:
            try:
                me = self._request('GET', self._url('/user'))
                self.config.metadata['login'] = me.get('login')
            except IntegrationError as e:
                if e.status not in (401, 403):
                    raise
                self._request('GET', self._url('/rate_limit'))
            logger.info("Connected to GitHub API: %s", self._api_url)
            self.config.status = IntegrationStatus.ACTIVE
            self._last_error = None
            return True
        except Exception as e:  # noqa: BLE001 - surface any connection error via status
            self._last_error = str(e)
            self.config.status = IntegrationStatus.ERROR
            return False
    
    def disconnect(self):
        """Disconnect from GitHub."""
        self._session = None
        self.config.status = IntegrationStatus.INACTIVE
    
    def health_check(self) -> Dict[str, Any]:
        """Check GitHub API reachability and rate-limit headroom."""
        result = {
            'status': self.config.status.value,
            'api_url': self._api_url,
            'last_error': self._last_error,
        }
        try:
            rate = self._request('GET', self._url('/rate_limit')).get('resources', {}).get('core', {})
            result['rate_limit'] = {'remaining': rate.get('remaining'), 'limit': rate.get('limit'), 'reset': rate.get('reset')}
            result['reachable'] = True
        except Exception as e:  # noqa: BLE001
            result['reachable'] = False
            result['error'] = str(e)
        return result
    
    # -- issues -----------------------------------------------------------------
    
    def create_issue(self,
                    owner: str,
                    repo: str,
                    title: str,
                    body: str,
                    labels: Optional[List[str]] = None,
                    assignees: Optional[List[str]] = None,
                    milestone: Optional[int] = None) -> Dict[str, Any]:
        """Create a GitHub issue."""
        payload: Dict[str, Any] = {'title': title, 'body': body}
        if labels:
            payload['labels'] = labels
        if assignees:
            payload['assignees'] = assignees
        if milestone is not None:
            payload['milestone'] = milestone
        issue = self._request('POST', self._url(f'/repos/{owner}/{repo}/issues'), json=payload)
        logger.info("Created GitHub issue: %s/%s#%s", owner, repo, issue.get('number'))
        return issue
    
    def get_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        return self._request('GET', self._url(f'/repos/{owner}/{repo}/issues/{issue_number}'))
    
    def update_issue(self, owner: str, repo: str, issue_number: int, **fields: Any) -> Dict[str, Any]:
        """Patch issue fields (title, body, state, labels, assignees, ...)."""
        return self._request('PATCH', self._url(f'/repos/{owner}/{repo}/issues/{issue_number}'), json=fields)
    
    def list_issues(self, owner: str, repo: str, state: str = 'open', labels: Optional[List[str]] = None,
                    per_page: int = 30, page: int = 1) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {'state': state, 'per_page': per_page, 'page': page}
        if labels:
            params['labels'] = ','.join(labels)
        return self._request('GET', self._url(f'/repos/{owner}/{repo}/issues'), params=params)
    
    # -- pull requests ----------------------------------------------------------
    
    def create_pull_request(self,
                           owner: str,
                           repo: str,
                           title: str,
                           body: str,
                           head: str,
                           base: str = "main",
                           draft: bool = False) -> Dict[str, Any]:
        """Create a pull request."""
        pr = self._request('POST', self._url(f'/repos/{owner}/{repo}/pulls'),
                           json={'title': title, 'body': body, 'head': head, 'base': base, 'draft': draft})
        logger.info("Created pull request: %s/%s#%s", owner, repo, pr.get('number'))
        return pr
    
    def merge_pull_request(self, owner: str, repo: str, number: int, method: str = 'squash',
                           commit_title: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {'merge_method': method}
        if commit_title:
            payload['commit_title'] = commit_title
        return self._request('PUT', self._url(f'/repos/{owner}/{repo}/pulls/{number}/merge'), json=payload)
    
    def list_pull_requests(self, owner: str, repo: str, state: str = 'open', per_page: int = 30) -> List[Dict[str, Any]]:
        return self._request('GET', self._url(f'/repos/{owner}/{repo}/pulls'), params={'state': state, 'per_page': per_page})
    
    # -- actions ----------------------------------------------------------------
    
    def trigger_workflow(self,
                        owner: str,
                        repo: str,
                        workflow_id: str,
                        ref: str = "main",
                        inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatch a GitHub Actions workflow (``workflow_id`` = numeric id or file name)."""
        payload: Dict[str, Any] = {'ref': ref}
        if inputs:
            payload['inputs'] = {k: str(v) for k, v in inputs.items()}
        wf = quote(str(workflow_id))
        self._request('POST', self._url(f'/repos/{owner}/{repo}/actions/workflows/{wf}/dispatches'), json=payload)
        logger.info("Triggered workflow %s on %s/%s@%s", workflow_id, owner, repo, ref)
        # The dispatch endpoint returns 204; report the newest run for this workflow.
        runs = self._request('GET', self._url(f'/repos/{owner}/{repo}/actions/workflows/{wf}/runs'),
                             params={'per_page': 1, 'branch': ref})
        latest = (runs.get('workflow_runs') or [{}])[0] if isinstance(runs, dict) else {}
        return {'workflow_id': workflow_id, 'ref': ref, 'inputs': inputs or {}, 'status': 'dispatched',
                'latest_run': latest}
    
    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> Dict[str, Any]:
        return self._request('GET', self._url(f'/repos/{owner}/{repo}/actions/runs/{run_id}'))
    
    # -- comments ---------------------------------------------------------------
    
    def add_comment(self,
                   owner: str,
                   repo: str,
                   issue_number: int,
                   body: str) -> Dict[str, Any]:
        """Add comment to issue/PR."""
        return self._request('POST', self._url(f'/repos/{owner}/{repo}/issues/{issue_number}/comments'), json={'body': body})
    
    # -- repos / search ---------------------------------------------------------
    
    def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        return self._request('GET', self._url(f'/repos/{owner}/{repo}'))
    
    def get_file_content(self, owner: str, repo: str, path: str, ref: Optional[str] = None) -> str:
        """Return decoded text content of a file in the repo."""
        params = {'ref': ref} if ref else None
        data = self._request('GET', self._url(f'/repos/{owner}/{repo}/contents/{quote(path)}'), params=params)
        if data.get('encoding') == 'base64':
            return base64.b64decode(data.get('content', '')).decode('utf-8', errors='replace')
        return data.get('content', '')
    
    def search_code(self,
                   query: str,
                   owner: Optional[str] = None,
                   repo: Optional[str] = None,
                   per_page: int = 30) -> List[Dict[str, Any]]:
        """Search code via ``GET /search/code``."""
        q = query
        if owner and repo:
            q += f" repo:{owner}/{repo}"
        elif owner:
            q += f" user:{owner}"
        data = self._request('GET', self._url('/search/code'), params={'q': q, 'per_page': per_page},
                             headers={'Accept': 'application/vnd.github.text-match+json'})
        return [{
            'name': item.get('name'),
            'path': item.get('path'),
            'repository': (item.get('repository') or {}).get('full_name'),
            'html_url': item.get('html_url'),
            'sha': item.get('sha'),
            'score': item.get('score'),
            'matches': [m.get('fragment') for m in item.get('text_matches', [])],
        } for item in data.get('items', [])]


__all__ = ['GitHubIntegration']
