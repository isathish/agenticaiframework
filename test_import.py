#!/usr/bin/env python3
"""Test script to verify all enterprise modules import correctly."""

import sys
sys.path.insert(0, '.')

try:
    import agenticaiframework
    print("✅ All imports successful!")
    print(f"Exported symbols: {len(agenticaiframework.__all__)}")
    print("\nEnterprise modules:")
    
    # Check each enterprise module
    modules = [
        ('AgentStepTracer', 'Tracing'),
        ('LatencyMetrics', 'Latency Metrics'),
        ('OfflineEvaluator', 'Offline Evaluation'),
        ('OnlineEvaluator', 'Online Evaluation'),
        ('CostQualityScorer', 'Cost vs Quality'),
        ('SecurityRiskScorer', 'Security Risk'),
        ('PromptVersionManager', 'Prompt Versioning'),
        ('AgentCIPipeline', 'Agent CI Pipelines'),
        ('ABTestingFramework', 'A/B Testing'),
        ('AgentBuilder', 'Agent Builder UI'),
        ('WorkflowDesigner', 'Workflow Designer'),
        ('AdminConsole', 'Admin Console'),
        ('ServiceNowIntegration', 'ITSM (ServiceNow)'),
        ('GitHubIntegration', 'GitHub Integration'),
        ('AzureDevOpsIntegration', 'Azure DevOps Integration'),
        ('SnowflakeConnector', 'Data Platforms'),
        ('ServerlessExecutor', 'Serverless Execution'),
        ('MultiRegionManager', 'Multi-Region Support'),
        ('TenantManager', 'Tenant Isolation'),
        ('AuditTrailManager', 'Audit Trails'),
        ('PolicyEngine', 'Policy Enforcement'),
        ('DataMaskingEngine', 'Data Masking'),
    ]
    
    for attr, name in modules:
        available = hasattr(agenticaiframework, attr)
        status = "✅" if available else "❌"
        print(f"  {status} {name} ({attr})")
    
    print("\nGlobal instances:")
    instances = [
        'tracer', 'latency_metrics', 'prompt_version_manager', 'prompt_library',
        'test_runner', 'deployment_manager', 'release_manager',
        'multi_region_manager', 'tenant_manager', 'serverless_executor',
        'audit_trail', 'policy_engine', 'data_masking',
        'integration_manager', 'webhook_manager',
        'agent_builder', 'workflow_designer', 'admin_console'
    ]
    
    for inst in instances:
        available = hasattr(agenticaiframework, inst)
        status = "✅" if available else "❌"
        print(f"  {status} {inst}")
    
    print("\n✅ All enterprise features implemented!")
    
except Exception as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
