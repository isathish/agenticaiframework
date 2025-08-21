"""
Agentic Framework SDK

A Python-based SDK for building agentic applications with lightweight, high-performance agents.
This framework provides comprehensive tools for creating, managing, and orchestrating agents
with built-in security, monitoring, observability, and fine-grained configuration options.
"""

__version__ = "0.1.0"
__author__ = "Agentic Framework Team"
__license__ = "MIT"

# Import core components for easy access
from .agents import Agent, AgentManager
from .prompts import Prompt, PromptTemplate, PromptManager
from .process import Process, ProcessScheduler
from .tasks import Task, TaskManager
from .mcp_tools import MCPTool, MCPToolManager
from .monitoring import PerformanceMonitor, EventTracer, AnomalyDetector
from .guardrails import ValidationGuardrail, PolicyEnforcer, RateLimiter
from .evaluation import AutomatedTester, HumanReviewEvaluator, EvaluationManager
from .knowledge import RAGRetriever, KnowledgeManager
from .llms import SimpleLLM, LLMSelector, LLMManager
from .communication import StreamtableHTTPProtocol, WebSocketProtocol, MessageQueueProtocol, CommunicationManager
from .memory import ShortTermMemoryStorage, LongTermMemoryStorage, ExternalMemoryStorage, SemanticIndex, MemoryManager
from .hub import AgentHub, PromptHub, MCPToolHub, GuardrailHub, LLMHub, HubManager
from .configurations import ConfigurationStore, ConfigurationManager
from .security import SecurityManager, SecurityLevel, SecurityError

# Define what is exposed when 'from agentic_framework import *' is used
__all__ = [
    "Agent", "AgentManager",
    "Prompt", "PromptTemplate", "PromptManager",
    "Process", "ProcessScheduler",
    "Task", "TaskManager",
    "MCPTool", "MCPToolManager",
    "PerformanceMonitor", "EventTracer", "AnomalyDetector",
    "ValidationGuardrail", "PolicyEnforcer", "RateLimiter",
    "AutomatedTester", "HumanReviewEvaluator", "EvaluationManager",
    "RAGRetriever", "KnowledgeManager",
    "SimpleLLM", "LLMSelector", "LLMManager",
    "StreamtableHTTPProtocol", "WebSocketProtocol", "MessageQueueProtocol", "CommunicationManager",
    "ShortTermMemoryStorage", "LongTermMemoryStorage", "ExternalMemoryStorage", "SemanticIndex", "MemoryManager",
    "AgentHub", "PromptHub", "MCPToolHub", "GuardrailHub", "LLMHub", "HubManager",
    "ConfigurationStore", "ConfigurationManager",
    "SecurityManager", "SecurityLevel", "SecurityError"
]

def initialize_framework(config: dict = None) -> dict:
    """
    Initialize the Agentic Framework with optional configuration.
    
    Args:
        config (dict, optional): Configuration dictionary for initializing framework components.
        
    Returns:
        dict: Dictionary of initialized core components for direct access.
    """
    if config is None:
        config = {}
    
    # Initialize core components with default or provided configurations
    security = SecurityManager(
        secret_key=config.get("secret_key", "default_secret_key"),
        security_level=config.get("security_level", SecurityLevel.MEDIUM)
    )
    agents = AgentManager(name="FrameworkAgentManager")
    prompts = PromptManager(name="FrameworkPromptManager")
    processes = ProcessScheduler(name="FrameworkProcessScheduler")
    tasks = TaskManager(name="FrameworkTaskManager")
    tools = MCPToolManager(name="FrameworkToolManager")
    monitoring = PerformanceMonitor(name="FrameworkPerformanceMonitor")
    guardrails = ValidationGuardrail(name="FrameworkGuardrail", validation_rules=config.get("guardrail_rules", {}))
    evaluation = EvaluationManager(name="FrameworkEvaluationManager", config={})
    knowledge = KnowledgeManager(name="FrameworkKnowledgeManager", config={})
    llms = LLMManager(name="FrameworkLLMManager", config={})
    communication = CommunicationManager(name="FrameworkCommunicationManager", config={})
    memory = MemoryManager(name="FrameworkMemoryManager", config={})
    hub = HubManager(name="FrameworkHubManager", config={})
    configurations = ConfigurationManager(name="FrameworkConfigManager", config={})
    
    # Return initialized components for use
    return {
        "security": security,
        "agents": agents,
        "prompts": prompts,
        "processes": processes,
        "tasks": tasks,
        "tools": tools,
        "monitoring": monitoring,
        "guardrails": guardrails,
        "evaluation": evaluation,
        "knowledge": knowledge,
        "llms": llms,
        "communication": communication,
        "memory": memory,
        "hub": hub,
        "configurations": configurations
    }
