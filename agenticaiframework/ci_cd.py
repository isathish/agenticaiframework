"""
CI/CD Pipeline Support for AI Agents.

Features:
- Agent CI pipelines
- Automated testing
- Deployment validation
- Release management
- Integration with CI/CD tools
"""

import uuid
import time
import logging
import json
import threading
import subprocess
import shutil
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PipelineStatus(Enum):
    """Pipeline execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageType(Enum):
    """Types of pipeline stages."""
    BUILD = "build"
    TEST = "test"
    LINT = "lint"
    SECURITY_SCAN = "security_scan"
    EVALUATION = "evaluation"
    DEPLOY = "deploy"
    CUSTOM = "custom"


@dataclass
class PipelineStage:
    """A stage in the CI/CD pipeline."""
    name: str
    stage_type: StageType
    commands: List[str]
    timeout_seconds: int = 300
    continue_on_failure: bool = False
    dependencies: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""
    stage_name: str
    status: PipelineStatus
    start_time: float
    end_time: float
    output: str
    error: Optional[str]
    artifacts: Dict[str, str]
    
    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time


@dataclass
class PipelineRun:
    """A pipeline execution run."""
    run_id: str
    pipeline_id: str
    trigger: str
    status: PipelineStatus
    start_time: float
    end_time: Optional[float]
    stage_results: Dict[str, StageResult]
    metadata: Dict[str, Any]


class AgentCIPipeline:
    """
    CI/CD pipeline for AI agents.
    
    Features:
    - Define build/test/deploy stages
    - Automatic evaluation runs
    - Security scanning
    - Deployment gates
    """
    
    def __init__(self, pipeline_id: str = None, name: str = None):
        self.pipeline_id = pipeline_id or str(uuid.uuid4())
        self.name = name or f"pipeline-{self.pipeline_id[:8]}"
        self.stages: Dict[str, PipelineStage] = {}
        self.stage_order: List[str] = []
        self.runs: List[PipelineRun] = []
        self.webhooks: List[str] = []
        self.environment: Dict[str, str] = {}
        
        # Callbacks
        self.on_stage_complete: Optional[Callable[[str, StageResult], None]] = None
        self.on_pipeline_complete: Optional[Callable[[PipelineRun], None]] = None
    
    def add_stage(self, stage: PipelineStage, position: int = None):
        """Add a stage to the pipeline."""
        self.stages[stage.name] = stage
        
        if position is not None and 0 <= position < len(self.stage_order):
            self.stage_order.insert(position, stage.name)
        else:
            self.stage_order.append(stage.name)
        
        logger.info("Added stage '%s' to pipeline '%s'", stage.name, self.name)
    
    def remove_stage(self, stage_name: str):
        """Remove a stage from the pipeline."""
        if stage_name in self.stages:
            del self.stages[stage_name]
            self.stage_order.remove(stage_name)
    
    def set_environment(self, env: Dict[str, str]):
        """Set pipeline-level environment variables."""
        self.environment.update(env)
    
    def run(self, 
           trigger: str = "manual",
           metadata: Dict[str, Any] = None,
           skip_stages: List[str] = None) -> PipelineRun:
        """
        Execute the pipeline.
        
        Args:
            trigger: What triggered the run (manual, webhook, schedule)
            metadata: Additional metadata
            skip_stages: Stages to skip
        """
        skip_stages = skip_stages or []
        
        run = PipelineRun(
            run_id=str(uuid.uuid4()),
            pipeline_id=self.pipeline_id,
            trigger=trigger,
            status=PipelineStatus.RUNNING,
            start_time=time.time(),
            end_time=None,
            stage_results={},
            metadata=metadata or {}
        )
        
        logger.info("Starting pipeline run %s (trigger: %s)", run.run_id, trigger)
        
        try:
            for stage_name in self.stage_order:
                if stage_name in skip_stages:
                    logger.info("Skipping stage '%s'", stage_name)
                    continue
                
                stage = self.stages[stage_name]
                
                # Check dependencies
                if not self._check_dependencies(stage, run.stage_results):
                    logger.warning("Stage '%s' dependencies not met", stage_name)
                    continue
                
                # Execute stage
                result = self._execute_stage(stage)
                run.stage_results[stage_name] = result
                
                if self.on_stage_complete:
                    self.on_stage_complete(stage_name, result)
                
                # Check for failure
                if result.status == PipelineStatus.FAILED and not stage.continue_on_failure:
                    run.status = PipelineStatus.FAILED
                    break
            else:
                run.status = PipelineStatus.SUCCESS
        
        except Exception as e:
            logger.error("Pipeline run failed: %s", e)
            run.status = PipelineStatus.FAILED
        
        finally:
            run.end_time = time.time()
            self.runs.append(run)
            
            if self.on_pipeline_complete:
                self.on_pipeline_complete(run)
        
        logger.info("Pipeline run %s completed with status: %s", 
                   run.run_id, run.status.value)
        
        return run
    
    def _check_dependencies(self, stage: PipelineStage, 
                           results: Dict[str, StageResult]) -> bool:
        """Check if stage dependencies are satisfied."""
        for dep in stage.dependencies:
            if dep not in results:
                return False
            if results[dep].status != PipelineStatus.SUCCESS:
                return False
        return True
    
    def _execute_stage(self, stage: PipelineStage) -> StageResult:
        """Execute a pipeline stage."""
        start_time = time.time()
        output_lines = []
        error = None
        artifacts = {}
        status = PipelineStatus.SUCCESS
        
        # Merge environment
        env = {**self.environment, **stage.environment}
        
        logger.info("Executing stage '%s'", stage.name)
        
        for command in stage.commands:
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=stage.timeout_seconds,
                    env={**dict(subprocess.os.environ), **env}
                )
                
                output_lines.append(f"$ {command}")
                output_lines.append(result.stdout)
                
                if result.returncode != 0:
                    output_lines.append(f"Error: {result.stderr}")
                    error = result.stderr
                    status = PipelineStatus.FAILED
                    break
                    
            except subprocess.TimeoutExpired:
                error = f"Command timed out after {stage.timeout_seconds}s"
                status = PipelineStatus.FAILED
                break
            except Exception as e:
                error = str(e)
                status = PipelineStatus.FAILED
                break
        
        # Collect artifacts
        for artifact_pattern in stage.artifacts:
            for path in Path('.').glob(artifact_pattern):
                artifacts[str(path)] = path.read_text() if path.is_file() else str(path)
        
        return StageResult(
            stage_name=stage.name,
            status=status,
            start_time=start_time,
            end_time=time.time(),
            output='\n'.join(output_lines),
            error=error,
            artifacts=artifacts
        )
    
    def get_run(self, run_id: str) -> Optional[PipelineRun]:
        """Get a pipeline run by ID."""
        for run in self.runs:
            if run.run_id == run_id:
                return run
        return None
    
    def get_runs(self, limit: int = 10) -> List[PipelineRun]:
        """Get recent pipeline runs."""
        return sorted(self.runs, key=lambda r: r.start_time, reverse=True)[:limit]
    
    def to_dict(self) -> Dict[str, Any]:
        """Export pipeline configuration."""
        return {
            'pipeline_id': self.pipeline_id,
            'name': self.name,
            'stages': [
                {
                    'name': s.name,
                    'type': s.stage_type.value,
                    'commands': s.commands,
                    'timeout': s.timeout_seconds,
                    'continue_on_failure': s.continue_on_failure,
                    'dependencies': s.dependencies,
                    'artifacts': s.artifacts
                }
                for s in [self.stages[n] for n in self.stage_order]
            ],
            'environment': self.environment
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentCIPipeline':
        """Create pipeline from configuration."""
        pipeline = cls(
            pipeline_id=data.get('pipeline_id'),
            name=data.get('name')
        )
        
        for stage_data in data.get('stages', []):
            stage = PipelineStage(
                name=stage_data['name'],
                stage_type=StageType(stage_data['type']),
                commands=stage_data['commands'],
                timeout_seconds=stage_data.get('timeout', 300),
                continue_on_failure=stage_data.get('continue_on_failure', False),
                dependencies=stage_data.get('dependencies', []),
                artifacts=stage_data.get('artifacts', [])
            )
            pipeline.add_stage(stage)
        
        pipeline.environment = data.get('environment', {})
        
        return pipeline


class AgentTestRunner:
    """
    Test runner for AI agent validation.
    
    Features:
    - Unit tests
    - Integration tests
    - Performance tests
    - Evaluation tests
    """
    
    def __init__(self):
        self.test_suites: Dict[str, List[Callable]] = {}
        self.fixtures: Dict[str, Callable] = {}
        self.results: List[Dict[str, Any]] = []
    
    def register_test(self, suite_name: str, test_fn: Callable):
        """Register a test function."""
        if suite_name not in self.test_suites:
            self.test_suites[suite_name] = []
        self.test_suites[suite_name].append(test_fn)
    
    def register_fixture(self, name: str, fixture_fn: Callable):
        """Register a test fixture."""
        self.fixtures[name] = fixture_fn
    
    def run_suite(self, suite_name: str) -> Dict[str, Any]:
        """Run a test suite."""
        if suite_name not in self.test_suites:
            return {'error': f"Suite '{suite_name}' not found"}
        
        suite_results = {
            'suite': suite_name,
            'start_time': time.time(),
            'tests': [],
            'passed': 0,
            'failed': 0,
            'errors': 0
        }
        
        for test_fn in self.test_suites[suite_name]:
            test_result = self._run_test(test_fn)
            suite_results['tests'].append(test_result)
            
            if test_result['status'] == 'passed':
                suite_results['passed'] += 1
            elif test_result['status'] == 'failed':
                suite_results['failed'] += 1
            else:
                suite_results['errors'] += 1
        
        suite_results['end_time'] = time.time()
        suite_results['duration'] = suite_results['end_time'] - suite_results['start_time']
        suite_results['total'] = len(suite_results['tests'])
        
        self.results.append(suite_results)
        
        return suite_results
    
    def _run_test(self, test_fn: Callable) -> Dict[str, Any]:
        """Run a single test."""
        result = {
            'name': test_fn.__name__,
            'start_time': time.time(),
            'status': 'passed',
            'message': None,
            'error': None
        }
        
        try:
            test_fn()
        except AssertionError as e:
            result['status'] = 'failed'
            result['message'] = str(e)
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        result['end_time'] = time.time()
        result['duration'] = result['end_time'] - result['start_time']
        
        return result
    
    def run_all(self) -> Dict[str, Any]:
        """Run all test suites."""
        all_results = {
            'start_time': time.time(),
            'suites': {},
            'summary': {'passed': 0, 'failed': 0, 'errors': 0, 'total': 0}
        }
        
        for suite_name in self.test_suites:
            suite_result = self.run_suite(suite_name)
            all_results['suites'][suite_name] = suite_result
            
            all_results['summary']['passed'] += suite_result['passed']
            all_results['summary']['failed'] += suite_result['failed']
            all_results['summary']['errors'] += suite_result['errors']
            all_results['summary']['total'] += suite_result['total']
        
        all_results['end_time'] = time.time()
        all_results['duration'] = all_results['end_time'] - all_results['start_time']
        
        return all_results
    
    def generate_report(self, format: str = 'text') -> str:
        """Generate test report."""
        if not self.results:
            return "No test results available"
        
        if format == 'json':
            return json.dumps(self.results, indent=2)
        
        # Text format
        lines = ["=" * 60, "TEST RESULTS", "=" * 60]
        
        total_passed = 0
        total_failed = 0
        total_errors = 0
        
        for suite_result in self.results:
            lines.append(f"\nSuite: {suite_result['suite']}")
            lines.append("-" * 40)
            
            for test in suite_result['tests']:
                status_symbol = {
                    'passed': '✓',
                    'failed': '✗',
                    'error': '!'
                }.get(test['status'], '?')
                
                lines.append(f"  {status_symbol} {test['name']} ({test['duration']:.3f}s)")
                
                if test['message']:
                    lines.append(f"    Message: {test['message']}")
                if test['error']:
                    lines.append(f"    Error: {test['error']}")
            
            total_passed += suite_result['passed']
            total_failed += suite_result['failed']
            total_errors += suite_result['errors']
        
        lines.append("\n" + "=" * 60)
        lines.append(f"TOTAL: {total_passed} passed, {total_failed} failed, {total_errors} errors")
        lines.append("=" * 60)
        
        return '\n'.join(lines)


class DeploymentManager:
    """
    Manages agent deployments.
    
    Features:
    - Deployment tracking
    - Rollback support
    - Health checks
    - Blue-green deployments
    """
    
    def __init__(self):
        self.deployments: Dict[str, Dict[str, Any]] = {}
        self.environments: Dict[str, Dict[str, Any]] = {}
        self.deployment_history: List[Dict[str, Any]] = []
    
    def register_environment(self, 
                            name: str,
                            config: Dict[str, Any]):
        """Register a deployment environment."""
        self.environments[name] = {
            'name': name,
            'config': config,
            'current_deployment': None,
            'created_at': time.time()
        }
        logger.info("Registered environment '%s'", name)
    
    def deploy(self,
              environment: str,
              version: str,
              artifacts: Dict[str, Any] = None,
              deployer: str = "system") -> Dict[str, Any]:
        """
        Deploy to an environment.
        
        Args:
            environment: Target environment
            version: Version to deploy
            artifacts: Deployment artifacts
            deployer: Who initiated deployment
        """
        if environment not in self.environments:
            raise ValueError(f"Environment '{environment}' not found")
        
        deployment_id = str(uuid.uuid4())
        
        deployment = {
            'deployment_id': deployment_id,
            'environment': environment,
            'version': version,
            'artifacts': artifacts or {},
            'deployer': deployer,
            'status': 'in_progress',
            'started_at': time.time(),
            'completed_at': None,
            'health_checks': []
        }
        
        logger.info("Starting deployment %s to %s (version: %s)",
                   deployment_id, environment, version)
        
        try:
            # Simulate deployment steps
            deployment['status'] = 'deployed'
            deployment['completed_at'] = time.time()
            
            # Update environment
            old_deployment = self.environments[environment].get('current_deployment')
            self.environments[environment]['current_deployment'] = deployment_id
            self.environments[environment]['current_version'] = version
            
            # Store for rollback
            if old_deployment:
                deployment['previous_deployment'] = old_deployment
            
        except Exception as e:
            deployment['status'] = 'failed'
            deployment['error'] = str(e)
            logger.error("Deployment failed: %s", e)
        
        self.deployments[deployment_id] = deployment
        self.deployment_history.append(deployment)
        
        return deployment
    
    def rollback(self, environment: str, deployer: str = "system") -> Dict[str, Any]:
        """Rollback to previous deployment."""
        if environment not in self.environments:
            raise ValueError(f"Environment '{environment}' not found")
        
        current_id = self.environments[environment].get('current_deployment')
        if not current_id:
            raise ValueError("No current deployment to rollback")
        
        current = self.deployments.get(current_id)
        if not current or 'previous_deployment' not in current:
            raise ValueError("No previous deployment available")
        
        previous = self.deployments.get(current['previous_deployment'])
        if not previous:
            raise ValueError("Previous deployment not found")
        
        logger.info("Rolling back %s from %s to %s",
                   environment, current['version'], previous['version'])
        
        return self.deploy(
            environment=environment,
            version=previous['version'],
            artifacts=previous.get('artifacts'),
            deployer=deployer
        )
    
    def check_health(self, environment: str) -> Dict[str, Any]:
        """Check deployment health."""
        if environment not in self.environments:
            return {'error': f"Environment '{environment}' not found"}
        
        env = self.environments[environment]
        deployment_id = env.get('current_deployment')
        
        if not deployment_id:
            return {'status': 'no_deployment', 'healthy': False}
        
        deployment = self.deployments.get(deployment_id)
        if not deployment:
            return {'status': 'deployment_not_found', 'healthy': False}
        
        # Perform health check (customizable)
        health = {
            'status': 'healthy' if deployment['status'] == 'deployed' else 'unhealthy',
            'deployment_id': deployment_id,
            'version': deployment['version'],
            'uptime': time.time() - deployment['completed_at'] if deployment['completed_at'] else 0,
            'checked_at': time.time()
        }
        
        deployment['health_checks'].append(health)
        
        return health
    
    def get_deployment(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """Get deployment details."""
        return self.deployments.get(deployment_id)
    
    def get_history(self, environment: str = None, 
                   limit: int = 10) -> List[Dict[str, Any]]:
        """Get deployment history."""
        history = self.deployment_history
        
        if environment:
            history = [d for d in history if d['environment'] == environment]
        
        return sorted(history, key=lambda d: d['started_at'], reverse=True)[:limit]


class ReleaseManager:
    """
    Manages releases and versions.
    
    Features:
    - Semantic versioning
    - Release notes
    - Change tracking
    - Release automation
    """
    
    def __init__(self):
        self.releases: Dict[str, Dict[str, Any]] = {}
        self.current_version: str = "0.0.0"
        self.release_branches: Dict[str, str] = {}
    
    def create_release(self,
                      version: str,
                      release_notes: str,
                      changes: List[Dict[str, Any]] = None,
                      created_by: str = "system") -> Dict[str, Any]:
        """
        Create a new release.
        
        Args:
            version: Semantic version (e.g., "1.2.3")
            release_notes: Release description
            changes: List of changes
            created_by: Creator
        """
        if not self._is_valid_version(version):
            raise ValueError(f"Invalid version format: {version}")
        
        if not self._is_newer_version(version, self.current_version):
            raise ValueError(f"Version {version} is not newer than {self.current_version}")
        
        release = {
            'version': version,
            'release_notes': release_notes,
            'changes': changes or [],
            'created_by': created_by,
            'created_at': time.time(),
            'status': 'draft',
            'artifacts': []
        }
        
        self.releases[version] = release
        logger.info("Created release %s", version)
        
        return release
    
    def _is_valid_version(self, version: str) -> bool:
        """Check if version is valid semantic version."""
        parts = version.split('.')
        if len(parts) != 3:
            return False
        return all(p.isdigit() for p in parts)
    
    def _is_newer_version(self, new: str, current: str) -> bool:
        """Check if new version is newer than current."""
        new_parts = [int(x) for x in new.split('.')]
        current_parts = [int(x) for x in current.split('.')]
        return new_parts > current_parts
    
    def publish_release(self, version: str) -> Dict[str, Any]:
        """Publish a release."""
        if version not in self.releases:
            raise ValueError(f"Release {version} not found")
        
        release = self.releases[version]
        release['status'] = 'published'
        release['published_at'] = time.time()
        
        self.current_version = version
        logger.info("Published release %s", version)
        
        return release
    
    def add_change(self, version: str, 
                  change_type: str,
                  description: str):
        """Add a change to a release."""
        if version not in self.releases:
            raise ValueError(f"Release {version} not found")
        
        self.releases[version]['changes'].append({
            'type': change_type,
            'description': description,
            'added_at': time.time()
        })
    
    def get_changelog(self, from_version: str = None) -> str:
        """Generate changelog."""
        lines = ["# Changelog\n"]
        
        sorted_versions = sorted(
            self.releases.keys(),
            key=lambda v: [int(x) for x in v.split('.')],
            reverse=True
        )
        
        for version in sorted_versions:
            if from_version and not self._is_newer_version(version, from_version):
                break
            
            release = self.releases[version]
            lines.append(f"\n## {version}")
            lines.append(f"Released: {datetime.fromtimestamp(release.get('published_at', release['created_at'])).isoformat()}\n")
            
            if release['release_notes']:
                lines.append(release['release_notes'])
            
            if release['changes']:
                lines.append("\n### Changes")
                for change in release['changes']:
                    lines.append(f"- **{change['type']}**: {change['description']}")
        
        return '\n'.join(lines)
    
    def get_release(self, version: str) -> Optional[Dict[str, Any]]:
        """Get release details."""
        return self.releases.get(version)
    
    def list_releases(self, status: str = None) -> List[Dict[str, Any]]:
        """List all releases."""
        releases = list(self.releases.values())
        
        if status:
            releases = [r for r in releases if r['status'] == status]
        
        return sorted(releases, key=lambda r: r['created_at'], reverse=True)


# Factory functions for common pipelines
def create_agent_pipeline(name: str, 
                         agent_path: str,
                         test_command: str = "pytest",
                         eval_dataset: str = None) -> AgentCIPipeline:
    """
    Create a standard agent CI pipeline.
    
    Includes:
    - Linting
    - Unit tests
    - Integration tests
    - Evaluation (if dataset provided)
    - Security scan
    """
    pipeline = AgentCIPipeline(name=name)
    
    # Lint stage
    pipeline.add_stage(PipelineStage(
        name="lint",
        stage_type=StageType.LINT,
        commands=[
            "pip install ruff",
            f"ruff check {agent_path}"
        ],
        timeout_seconds=120
    ))
    
    # Test stage
    pipeline.add_stage(PipelineStage(
        name="test",
        stage_type=StageType.TEST,
        commands=[
            "pip install pytest pytest-cov",
            f"{test_command} --cov={agent_path}"
        ],
        dependencies=["lint"],
        artifacts=["coverage.xml", "*.html"]
    ))
    
    # Security scan
    pipeline.add_stage(PipelineStage(
        name="security",
        stage_type=StageType.SECURITY_SCAN,
        commands=[
            "pip install bandit",
            f"bandit -r {agent_path}"
        ],
        dependencies=["test"],
        continue_on_failure=True
    ))
    
    # Evaluation (if dataset provided)
    if eval_dataset:
        pipeline.add_stage(PipelineStage(
            name="evaluation",
            stage_type=StageType.EVALUATION,
            commands=[
                f"python -m agenticaiframework.evaluation --dataset {eval_dataset}"
            ],
            dependencies=["test"],
            timeout_seconds=600
        ))
    
    return pipeline


# Global instances
test_runner = AgentTestRunner()
deployment_manager = DeploymentManager()
release_manager = ReleaseManager()
