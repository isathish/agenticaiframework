"""
AgenticAI Framework - Evaluation Package.

Comprehensive evaluation system for AI agents:
- Offline/Online evaluation
- Cost and quality scoring
- Security and risk assessment
- A/B testing and canary deployments
- Memory, RAG, and workflow evaluation
- Prompt drift detection
- Model tier evaluation (SLM/MLM/LLM/RLM)
"""

# Types
from .types import EvaluationType, EvaluationResult

# Core evaluators
from .offline import OfflineEvaluator
from .online import OnlineEvaluator

# Quality and cost scoring
from .cost_quality import CostQualityScorer
from .security_risk import SecurityRiskScorer

# Testing frameworks
from .ab_testing import ABTestingFramework
from .canary import CanaryDeploymentManager

# Model evaluation
from .model_quality import ModelQualityEvaluator
from .model_tier import ModelTierEvaluator, model_tier_evaluator

# Task and tool evaluation
from .task_tool import TaskEvaluator, ToolInvocationEvaluator

# System evaluation
from .workflow import WorkflowEvaluator
from .memory_rag import MemoryEvaluator, RAGEvaluator

# Autonomy and performance
from .autonomy_performance import AutonomyEvaluator, PerformanceEvaluator

# Human and business
from .human_business import HITLEvaluator, BusinessOutcomeEvaluator

# Drift detection
from .drift import (
    DriftType,
    DriftSeverity,
    DriftAlert,
    PromptDriftDetector,
    prompt_drift_detector
)

__all__ = [
    # Types
    'EvaluationType',
    'EvaluationResult',
    
    # Core evaluators
    'OfflineEvaluator',
    'OnlineEvaluator',
    
    # Quality and cost
    'CostQualityScorer',
    'SecurityRiskScorer',
    
    # Testing
    'ABTestingFramework',
    'CanaryDeploymentManager',
    
    # Model evaluation
    'ModelQualityEvaluator',
    'ModelTierEvaluator',
    'model_tier_evaluator',
    
    # Task and tool
    'TaskEvaluator',
    'ToolInvocationEvaluator',
    
    # System evaluation
    'WorkflowEvaluator',
    'MemoryEvaluator',
    'RAGEvaluator',
    
    # Autonomy and performance
    'AutonomyEvaluator',
    'PerformanceEvaluator',
    
    # Human and business
    'HITLEvaluator',
    'BusinessOutcomeEvaluator',
    
    # Drift detection
    'DriftType',
    'DriftSeverity',
    'DriftAlert',
    'PromptDriftDetector',
    'prompt_drift_detector',
]
