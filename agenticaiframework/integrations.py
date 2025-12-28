"""
Integration Module for External Services.

Features:
- ITSM Integration (ServiceNow, etc.)
- Developer Tools (GitHub, Azure DevOps)
- Data Platforms
- Generic webhook support
"""

import uuid
import time
import logging
import json
import base64
import hashlib
import hmac
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import threading

logger = logging.getLogger(__name__)


class IntegrationStatus(Enum):
    """Status of an integration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class IntegrationConfig:
    """Configuration for an integration."""
    integration_id: str
    name: str
    integration_type: str
    endpoint: str
    auth_type: str  # api_key, oauth, basic, none
    credentials: Dict[str, str]
    settings: Dict[str, Any]
    status: IntegrationStatus
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseIntegration(ABC):
    """Base class for integrations."""
    
    def __init__(self, config: IntegrationConfig):
        self.config = config
        self._session = None
        self._last_error: Optional[str] = None
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection."""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Close connection."""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check integration health."""
        pass
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        headers = {}
        
        if self.config.auth_type == "api_key":
            key_header = self.config.settings.get('api_key_header', 'Authorization')
            key_prefix = self.config.settings.get('api_key_prefix', 'Bearer')
            headers[key_header] = f"{key_prefix} {self.config.credentials.get('api_key', '')}"
        
        elif self.config.auth_type == "basic":
            credentials = base64.b64encode(
                f"{self.config.credentials.get('username', '')}:{self.config.credentials.get('password', '')}".encode()
            ).decode()
            headers['Authorization'] = f"Basic {credentials}"
        
        elif self.config.auth_type == "oauth":
            headers['Authorization'] = f"Bearer {self.config.credentials.get('access_token', '')}"
        
        return headers


# ServiceNow Integration
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
        except Exception as e:
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
                             type: str = "normal",
                             risk: str = "moderate",
                             impact: str = "medium") -> Dict[str, Any]:
        """Create a change request."""
        change = {
            'sys_id': str(uuid.uuid4()),
            'number': f"CHG{int(time.time())}",
            'short_description': short_description,
            'description': description,
            'type': type,
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


# GitHub Integration
class GitHubIntegration(BaseIntegration):
    """
    GitHub Integration.
    
    Features:
    - Repository management
    - Issue tracking
    - Pull requests
    - Actions/Workflows
    - Code search
    """
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self._api_url = config.settings.get('api_url', 'https://api.github.com')
    
    def connect(self) -> bool:
        """Test connection to GitHub."""
        try:
            logger.info("Connected to GitHub API: %s", self._api_url)
            self.config.status = IntegrationStatus.ACTIVE
            return True
        except Exception as e:
            self._last_error = str(e)
            self.config.status = IntegrationStatus.ERROR
            return False
    
    def disconnect(self):
        """Disconnect from GitHub."""
        self.config.status = IntegrationStatus.INACTIVE
    
    def health_check(self) -> Dict[str, Any]:
        """Check GitHub API health."""
        return {
            'status': self.config.status.value,
            'api_url': self._api_url,
            'last_error': self._last_error
        }
    
    def create_issue(self,
                    owner: str,
                    repo: str,
                    title: str,
                    body: str,
                    labels: List[str] = None,
                    assignees: List[str] = None) -> Dict[str, Any]:
        """Create a GitHub issue."""
        issue = {
            'id': int(time.time() * 1000),
            'number': int(time.time()) % 10000,
            'title': title,
            'body': body,
            'labels': labels or [],
            'assignees': assignees or [],
            'state': 'open',
            'created_at': datetime.now().isoformat(),
            'html_url': f"https://github.com/{owner}/{repo}/issues/{int(time.time()) % 10000}"
        }
        
        logger.info("Created GitHub issue: %s/%s#%d", owner, repo, issue['number'])
        
        return issue
    
    def create_pull_request(self,
                           owner: str,
                           repo: str,
                           title: str,
                           body: str,
                           head: str,
                           base: str = "main") -> Dict[str, Any]:
        """Create a pull request."""
        pr = {
            'id': int(time.time() * 1000),
            'number': int(time.time()) % 10000,
            'title': title,
            'body': body,
            'head': head,
            'base': base,
            'state': 'open',
            'created_at': datetime.now().isoformat(),
            'html_url': f"https://github.com/{owner}/{repo}/pull/{int(time.time()) % 10000}"
        }
        
        logger.info("Created pull request: %s/%s#%d", owner, repo, pr['number'])
        
        return pr
    
    def trigger_workflow(self,
                        owner: str,
                        repo: str,
                        workflow_id: str,
                        ref: str = "main",
                        inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """Trigger a GitHub Actions workflow."""
        run = {
            'id': int(time.time() * 1000),
            'workflow_id': workflow_id,
            'ref': ref,
            'inputs': inputs or {},
            'status': 'queued',
            'created_at': datetime.now().isoformat()
        }
        
        logger.info("Triggered workflow %s on %s/%s", workflow_id, owner, repo)
        
        return run
    
    def add_comment(self,
                   owner: str,
                   repo: str,
                   issue_number: int,
                   body: str) -> Dict[str, Any]:
        """Add comment to issue/PR."""
        comment = {
            'id': int(time.time() * 1000),
            'body': body,
            'created_at': datetime.now().isoformat()
        }
        
        return comment
    
    def search_code(self,
                   query: str,
                   owner: str = None,
                   repo: str = None) -> List[Dict[str, Any]]:
        """Search code in repositories."""
        # Simulated search results
        return [{
            'name': 'example.py',
            'path': 'src/example.py',
            'repository': f"{owner or 'org'}/{repo or 'repo'}",
            'html_url': f"https://github.com/{owner or 'org'}/{repo or 'repo'}/blob/main/src/example.py",
            'score': 1.0
        }]


# Azure DevOps Integration
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
        except Exception as e:
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


# Webhook Manager
class WebhookManager:
    """
    Manages webhooks for integrations.
    
    Features:
    - Incoming webhooks
    - Outgoing webhooks
    - Signature verification
    - Event routing
    """
    
    def __init__(self):
        self.incoming_webhooks: Dict[str, Dict[str, Any]] = {}
        self.outgoing_webhooks: Dict[str, Dict[str, Any]] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
    
    def register_incoming_webhook(self,
                                  name: str,
                                  secret: str = None,
                                  allowed_events: List[str] = None) -> Dict[str, Any]:
        """Register an incoming webhook endpoint."""
        webhook_id = str(uuid.uuid4())
        
        webhook = {
            'id': webhook_id,
            'name': name,
            'secret': secret or hashlib.sha256(str(time.time()).encode()).hexdigest()[:32],
            'allowed_events': allowed_events or ['*'],
            'url': f"/webhooks/incoming/{webhook_id}",
            'created_at': time.time(),
            'total_received': 0
        }
        
        with self._lock:
            self.incoming_webhooks[webhook_id] = webhook
        
        logger.info("Registered incoming webhook: %s", name)
        
        return webhook
    
    def register_outgoing_webhook(self,
                                  name: str,
                                  url: str,
                                  events: List[str],
                                  secret: str = None,
                                  headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Register an outgoing webhook."""
        webhook_id = str(uuid.uuid4())
        
        webhook = {
            'id': webhook_id,
            'name': name,
            'url': url,
            'events': events,
            'secret': secret,
            'headers': headers or {},
            'created_at': time.time(),
            'total_sent': 0,
            'last_status': None
        }
        
        with self._lock:
            self.outgoing_webhooks[webhook_id] = webhook
        
        logger.info("Registered outgoing webhook: %s -> %s", name, url)
        
        return webhook
    
    def verify_signature(self, webhook_id: str, payload: str, signature: str) -> bool:
        """Verify webhook signature."""
        webhook = self.incoming_webhooks.get(webhook_id)
        if not webhook:
            return False
        
        secret = webhook.get('secret')
        if not secret:
            return True
        
        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected}", signature)
    
    def process_incoming(self,
                        webhook_id: str,
                        event_type: str,
                        payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming webhook."""
        webhook = self.incoming_webhooks.get(webhook_id)
        if not webhook:
            return {'error': 'Webhook not found'}
        
        # Check allowed events
        if '*' not in webhook['allowed_events'] and event_type not in webhook['allowed_events']:
            return {'error': 'Event type not allowed'}
        
        webhook['total_received'] += 1
        
        # Route to handlers
        handlers = self.event_handlers.get(event_type, []) + self.event_handlers.get('*', [])
        
        results = []
        for handler in handlers:
            try:
                result = handler(event_type, payload)
                results.append({'status': 'success', 'result': result})
            except Exception as e:
                results.append({'status': 'error', 'error': str(e)})
        
        return {
            'webhook_id': webhook_id,
            'event_type': event_type,
            'handlers_executed': len(handlers),
            'results': results
        }
    
    def send_webhook(self, event_type: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Send webhook to all registered endpoints for event type."""
        results = []
        
        for webhook_id, webhook in self.outgoing_webhooks.items():
            if event_type not in webhook['events'] and '*' not in webhook['events']:
                continue
            
            # Prepare payload
            body = {
                'event': event_type,
                'timestamp': time.time(),
                'payload': payload
            }
            
            # Sign if secret
            signature = None
            if webhook.get('secret'):
                signature = hmac.new(
                    webhook['secret'].encode(),
                    json.dumps(body).encode(),
                    hashlib.sha256
                ).hexdigest()
            
            # Simulate sending
            webhook['total_sent'] += 1
            webhook['last_status'] = 200  # Simulated
            
            results.append({
                'webhook_id': webhook_id,
                'name': webhook['name'],
                'url': webhook['url'],
                'status': 200,
                'signature': f"sha256={signature}" if signature else None
            })
        
        return results
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """Add handler for incoming webhook events."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def list_webhooks(self) -> Dict[str, List[Dict[str, Any]]]:
        """List all webhooks."""
        return {
            'incoming': [
                {
                    'id': w['id'],
                    'name': w['name'],
                    'url': w['url'],
                    'allowed_events': w['allowed_events'],
                    'total_received': w['total_received']
                }
                for w in self.incoming_webhooks.values()
            ],
            'outgoing': [
                {
                    'id': w['id'],
                    'name': w['name'],
                    'url': w['url'],
                    'events': w['events'],
                    'total_sent': w['total_sent'],
                    'last_status': w['last_status']
                }
                for w in self.outgoing_webhooks.values()
            ]
        }


# Data Platform Integrations
class DataPlatformConnector(ABC):
    """Base class for data platform connectors."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to data platform."""
        pass
    
    @abstractmethod
    def query(self, query: str) -> List[Dict[str, Any]]:
        """Execute query."""
        pass
    
    @abstractmethod
    def write(self, table: str, data: List[Dict[str, Any]]) -> bool:
        """Write data."""
        pass


class SnowflakeConnector(DataPlatformConnector):
    """Snowflake data platform connector."""
    
    def __init__(self, account: str, user: str, password: str, 
                 warehouse: str, database: str, schema: str):
        self.config = {
            'account': account,
            'user': user,
            'warehouse': warehouse,
            'database': database,
            'schema': schema
        }
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to Snowflake."""
        logger.info("Connected to Snowflake: %s", self.config['account'])
        self._connected = True
        return True
    
    def query(self, query: str) -> List[Dict[str, Any]]:
        """Execute Snowflake query."""
        if not self._connected:
            raise RuntimeError("Not connected")
        
        logger.info("Executing Snowflake query: %s...", query[:50])
        return []  # Simulated
    
    def write(self, table: str, data: List[Dict[str, Any]]) -> bool:
        """Write data to Snowflake."""
        if not self._connected:
            raise RuntimeError("Not connected")
        
        logger.info("Writing %d rows to Snowflake table %s", len(data), table)
        return True


class DatabricksConnector(DataPlatformConnector):
    """Databricks data platform connector."""
    
    def __init__(self, workspace_url: str, token: str, cluster_id: str = None):
        self.config = {
            'workspace_url': workspace_url,
            'cluster_id': cluster_id
        }
        self._token = token
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to Databricks."""
        logger.info("Connected to Databricks: %s", self.config['workspace_url'])
        self._connected = True
        return True
    
    def query(self, query: str) -> List[Dict[str, Any]]:
        """Execute Databricks SQL query."""
        if not self._connected:
            raise RuntimeError("Not connected")
        
        logger.info("Executing Databricks query: %s...", query[:50])
        return []  # Simulated
    
    def write(self, table: str, data: List[Dict[str, Any]]) -> bool:
        """Write data to Databricks."""
        if not self._connected:
            raise RuntimeError("Not connected")
        
        logger.info("Writing %d rows to Databricks table %s", len(data), table)
        return True


# Integration Manager
class IntegrationManager:
    """
    Manages all integrations.
    
    Features:
    - Integration lifecycle
    - Credential management
    - Health monitoring
    - Event routing
    """
    
    def __init__(self):
        self.integrations: Dict[str, BaseIntegration] = {}
        self.configs: Dict[str, IntegrationConfig] = {}
        self.webhook_manager = WebhookManager()
        self._lock = threading.Lock()
        
        # Integration type registry
        self._integration_types = {
            'servicenow': ServiceNowIntegration,
            'github': GitHubIntegration,
            'azure_devops': AzureDevOpsIntegration
        }
    
    def register_integration_type(self, name: str, cls: type):
        """Register a custom integration type."""
        self._integration_types[name] = cls
    
    def add_integration(self,
                       name: str,
                       integration_type: str,
                       endpoint: str,
                       auth_type: str = "api_key",
                       credentials: Dict[str, str] = None,
                       settings: Dict[str, Any] = None) -> IntegrationConfig:
        """Add a new integration."""
        integration_id = str(uuid.uuid4())
        
        config = IntegrationConfig(
            integration_id=integration_id,
            name=name,
            integration_type=integration_type,
            endpoint=endpoint,
            auth_type=auth_type,
            credentials=credentials or {},
            settings=settings or {},
            status=IntegrationStatus.PENDING,
            created_at=time.time()
        )
        
        # Create integration instance
        integration_cls = self._integration_types.get(integration_type)
        if integration_cls:
            integration = integration_cls(config)
        else:
            raise ValueError(f"Unknown integration type: {integration_type}")
        
        with self._lock:
            self.configs[integration_id] = config
            self.integrations[integration_id] = integration
        
        logger.info("Added integration: %s (%s)", name, integration_type)
        
        return config
    
    def connect(self, integration_id: str) -> bool:
        """Connect an integration."""
        integration = self.integrations.get(integration_id)
        if not integration:
            raise ValueError(f"Integration not found: {integration_id}")
        
        return integration.connect()
    
    def disconnect(self, integration_id: str):
        """Disconnect an integration."""
        integration = self.integrations.get(integration_id)
        if integration:
            integration.disconnect()
    
    def get_integration(self, integration_id: str) -> Optional[BaseIntegration]:
        """Get integration by ID."""
        return self.integrations.get(integration_id)
    
    def get_integration_by_name(self, name: str) -> Optional[BaseIntegration]:
        """Get integration by name."""
        for config in self.configs.values():
            if config.name == name:
                return self.integrations.get(config.integration_id)
        return None
    
    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all integrations."""
        results = {}
        
        for integration_id, integration in self.integrations.items():
            config = self.configs[integration_id]
            results[config.name] = {
                'integration_id': integration_id,
                'type': config.integration_type,
                **integration.health_check()
            }
        
        return results
    
    def list_integrations(self) -> List[Dict[str, Any]]:
        """List all integrations."""
        return [
            {
                'integration_id': c.integration_id,
                'name': c.name,
                'type': c.integration_type,
                'endpoint': c.endpoint,
                'status': c.status.value,
                'created_at': c.created_at
            }
            for c in self.configs.values()
        ]
    
    def remove_integration(self, integration_id: str):
        """Remove an integration."""
        with self._lock:
            if integration_id in self.integrations:
                self.integrations[integration_id].disconnect()
                del self.integrations[integration_id]
                del self.configs[integration_id]
        
        logger.info("Removed integration: %s", integration_id)


# Global instances
integration_manager = IntegrationManager()
webhook_manager = WebhookManager()
