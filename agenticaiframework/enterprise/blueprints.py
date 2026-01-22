"""
Enterprise Blueprints - Pre-built agent configurations for common use cases.

Blueprints provide ready-to-use agent configurations that can be
instantiated with minimal code.

Usage:
    >>> from agenticaiframework.enterprise.blueprints import RequirementsAgent
    >>> 
    >>> agent = RequirementsAgent()
    >>> result = await agent.analyze("Build an e-commerce platform")
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


# =============================================================================
# Blueprint Base
# =============================================================================

@dataclass
class BlueprintConfig:
    """Configuration for blueprint agents."""
    name: str
    role: str
    capabilities: List[str] = field(default_factory=list)
    model: str = "gpt-4o"
    provider: str = "azure"
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: str = ""


class BlueprintAgent:
    """
    Base class for blueprint agents.
    
    Provides a consistent interface for all pre-built agents.
    """
    
    config: BlueprintConfig
    
    def __init__(
        self,
        *,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs,
    ):
        self.model = model or self.config.model
        self.provider = provider or self.config.provider
        self._client = None
        self._history: List[Dict] = []
        self._kwargs = kwargs
    
    def _get_client(self):
        """Get or create LLM client."""
        if self._client is None:
            if self.provider == "azure":
                try:
                    from openai import AzureOpenAI
                    self._client = AzureOpenAI(
                        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                        api_version="2024-02-01",
                    )
                except ImportError:
                    raise ImportError("openai is required. Install with: pip install openai")
        return self._client
    
    async def _call_llm(self, prompt: str, system: Optional[str] = None) -> str:
        """Call LLM with the prompt."""
        client = self._get_client()
        
        messages = []
        if system or self.config.system_prompt:
            messages.append({
                "role": "system",
                "content": system or self.config.system_prompt,
            })
        messages.append({"role": "user", "content": prompt})
        
        params = {
            "model": self.model,
            "messages": messages,
        }
        
        # Handle model-specific parameters
        if "gpt-5" in self.model.lower():
            params["max_completion_tokens"] = self.config.max_tokens
            params["temperature"] = 1
        else:
            params["max_tokens"] = self.config.max_tokens
            params["temperature"] = self.config.temperature
        
        response = await asyncio.to_thread(
            lambda: client.chat.completions.create(**params)
        )
        
        return response.choices[0].message.content
    
    async def invoke(self, prompt: str) -> str:
        """
        Invoke the agent with a prompt.
        
        Args:
            prompt: User prompt
            
        Returns:
            Agent response
        """
        return await self._call_llm(prompt)
    
    def invoke_sync(self, prompt: str) -> str:
        """Synchronous version of invoke."""
        return asyncio.run(self.invoke(prompt))


# =============================================================================
# SDLC Blueprint Agents
# =============================================================================

class RequirementsAgent(BlueprintAgent):
    """
    Pre-built Requirements Analyst agent.
    
    Analyzes project descriptions and creates structured requirements
    including functional requirements, non-functional requirements,
    and user stories.
    
    Usage:
        >>> agent = RequirementsAgent()
        >>> result = await agent.analyze("Build an e-commerce platform")
    """
    
    config = BlueprintConfig(
        name="RequirementsAgent",
        role="Requirements Analyst",
        capabilities=["requirements-analysis", "user-stories", "use-cases"],
        system_prompt="""You are an expert Requirements Analyst with deep experience in software development.
Your task is to analyze project descriptions and create comprehensive, structured requirements.

Always include:
1. Functional Requirements (FR-001, FR-002, etc.)
2. Non-Functional Requirements (NFR-001, etc.)
3. User Stories in format: "As a [user], I want [feature] so that [benefit]"
4. Acceptance Criteria for each requirement
5. Priority levels (Must Have, Should Have, Nice to Have)
6. Dependencies between requirements

Format your output as clean, structured markdown.""",
    )
    
    async def analyze(self, description: str) -> str:
        """Analyze a project description and generate requirements."""
        prompt = f"""Analyze the following project and create detailed software requirements:

{description}

Provide comprehensive requirements in structured markdown format."""
        return await self.invoke(prompt)


class DesignAgent(BlueprintAgent):
    """
    Pre-built Software Architect agent.
    
    Creates technical designs including architecture, database schemas,
    and API specifications.
    
    Usage:
        >>> agent = DesignAgent()
        >>> result = await agent.design(requirements)
    """
    
    config = BlueprintConfig(
        name="DesignAgent",
        role="Software Architect",
        capabilities=["architecture", "database-design", "api-design"],
        system_prompt="""You are an expert Software Architect with experience in scalable, maintainable systems.
Your task is to create comprehensive technical designs based on requirements.

Always include:
1. System Architecture with component diagram description
2. Database Design (tables, relationships, indexes)
3. API Design (endpoints, methods, request/response schemas)
4. Technology Stack recommendations with justification
5. Security considerations
6. Scalability and performance strategies
7. Error handling approach

Format your output as clean, structured markdown with code examples where appropriate.""",
    )
    
    async def design(self, requirements: str) -> str:
        """Create a technical design based on requirements."""
        prompt = f"""Based on the following requirements, create a comprehensive technical design:

{requirements}

Provide a detailed technical design document in markdown format."""
        return await self.invoke(prompt)


class DevelopmentAgent(BlueprintAgent):
    """
    Pre-built Senior Developer agent.
    
    Generates production-quality code based on technical designs.
    
    Usage:
        >>> agent = DevelopmentAgent()
        >>> result = await agent.implement(design)
    """
    
    config = BlueprintConfig(
        name="DevelopmentAgent",
        role="Senior Software Developer",
        capabilities=["code-generation", "refactoring", "best-practices"],
        max_tokens=8192,
        system_prompt="""You are a Senior Software Developer with expertise in clean code and best practices.
Your task is to implement production-quality code based on technical designs.

Always follow:
1. Clean Code principles (SOLID, DRY, KISS)
2. Comprehensive error handling
3. Logging and monitoring hooks
4. Configuration management
5. Security best practices
6. Performance considerations
7. Proper documentation

Provide complete, runnable code with comments explaining complex logic.""",
    )
    
    async def implement(self, design: str) -> str:
        """Implement code based on a technical design."""
        prompt = f"""Based on the following technical design, implement production-quality code:

{design}

Provide complete, well-documented code with proper error handling."""
        return await self.invoke(prompt)


class TestingAgent(BlueprintAgent):
    """
    Pre-built QA Engineer agent.
    
    Creates test strategies, test cases, and test automation code.
    
    Usage:
        >>> agent = TestingAgent()
        >>> result = await agent.create_tests(code)
    """
    
    config = BlueprintConfig(
        name="TestingAgent",
        role="QA Engineer",
        capabilities=["test-strategy", "test-cases", "automation"],
        system_prompt="""You are an expert QA Engineer with deep experience in testing methodologies.
Your task is to create comprehensive testing strategies and test cases.

Always include:
1. Test Strategy document
2. Unit test cases with expected results
3. Integration test scenarios
4. Edge case coverage
5. Performance test considerations
6. Security test checklist
7. Test data requirements

Format as structured markdown with actual test code where appropriate.""",
    )
    
    async def create_tests(self, implementation: str) -> str:
        """Create test strategy and test cases."""
        prompt = f"""Based on the following implementation, create a comprehensive test strategy:

{implementation}

Provide test strategy and test cases in markdown format with test code."""
        return await self.invoke(prompt)


class SecurityAgent(BlueprintAgent):
    """
    Pre-built Security Analyst agent.
    
    Performs security analysis and provides recommendations.
    
    Usage:
        >>> agent = SecurityAgent()
        >>> result = await agent.analyze(code)
    """
    
    config = BlueprintConfig(
        name="SecurityAgent",
        role="Security Analyst",
        capabilities=["threat-modeling", "vulnerability-analysis", "security-review"],
        system_prompt="""You are an expert Security Analyst with experience in application security.
Your task is to perform security analysis and provide actionable recommendations.

Always include:
1. Threat Model (STRIDE analysis)
2. Vulnerability Assessment
3. Security Requirements
4. Authentication/Authorization review
5. Data protection recommendations
6. Input validation analysis
7. Compliance considerations (GDPR, SOC2, etc.)

Format as structured markdown with severity ratings and remediation steps.""",
    )
    
    async def analyze(self, implementation: str) -> str:
        """Perform security analysis."""
        prompt = f"""Perform a comprehensive security analysis on the following:

{implementation}

Provide a security report with vulnerabilities and recommendations."""
        return await self.invoke(prompt)


class DeploymentAgent(BlueprintAgent):
    """
    Pre-built DevOps Engineer agent.
    
    Creates deployment configurations and infrastructure code.
    
    Usage:
        >>> agent = DeploymentAgent()
        >>> result = await agent.create_deployment(project)
    """
    
    config = BlueprintConfig(
        name="DeploymentAgent",
        role="DevOps Engineer",
        capabilities=["containerization", "ci-cd", "infrastructure"],
        system_prompt="""You are an expert DevOps Engineer with experience in cloud deployments.
Your task is to create deployment configurations and infrastructure code.

Always include:
1. Dockerfile (multi-stage, optimized)
2. docker-compose.yml
3. Kubernetes manifests (if applicable)
4. CI/CD pipeline configuration (GitHub Actions)
5. Infrastructure as Code (Terraform/Bicep)
6. Environment configuration
7. Monitoring and alerting setup

Provide production-ready configuration files with comments.""",
    )
    
    async def create_deployment(self, project: str) -> str:
        """Create deployment configuration."""
        prompt = f"""Create comprehensive deployment configuration for:

{project}

Provide all necessary deployment files with comments."""
        return await self.invoke(prompt)


class DocumentationAgent(BlueprintAgent):
    """
    Pre-built Technical Writer agent.
    
    Creates comprehensive project documentation.
    
    Usage:
        >>> agent = DocumentationAgent()
        >>> result = await agent.document(project)
    """
    
    config = BlueprintConfig(
        name="DocumentationAgent",
        role="Technical Writer",
        capabilities=["documentation", "api-docs", "user-guides"],
        system_prompt="""You are an expert Technical Writer with experience in software documentation.
Your task is to create comprehensive, user-friendly documentation.

Always include:
1. README.md with quick start guide
2. API documentation with examples
3. Architecture documentation
4. Configuration guide
5. Troubleshooting section
6. Contributing guidelines

Format as clean, accessible markdown with code examples.""",
    )
    
    async def document(self, project: str) -> str:
        """Create project documentation."""
        prompt = f"""Create comprehensive documentation for:

{project}

Provide complete documentation in markdown format."""
        return await self.invoke(prompt)


class ReviewAgent(BlueprintAgent):
    """
    Pre-built Code Reviewer agent.
    
    Reviews code and provides feedback.
    
    Usage:
        >>> agent = ReviewAgent()
        >>> result = await agent.review(code)
    """
    
    config = BlueprintConfig(
        name="ReviewAgent",
        role="Senior Code Reviewer",
        capabilities=["code-review", "best-practices", "quality-assurance"],
        system_prompt="""You are an expert Code Reviewer with deep experience in software quality.
Your task is to review code and provide constructive feedback.

Always check for:
1. Code quality and readability
2. Best practices compliance
3. Security vulnerabilities
4. Performance issues
5. Error handling completeness
6. Test coverage
7. Documentation quality

Format as structured markdown with severity ratings and specific recommendations.""",
    )
    
    async def review(self, code: str) -> str:
        """Review code and provide feedback."""
        prompt = f"""Review the following code and provide detailed feedback:

{code}

Provide a structured review with recommendations."""
        return await self.invoke(prompt)


# =============================================================================
# Utility Blueprint Agents
# =============================================================================

class AnalystAgent(BlueprintAgent):
    """General data analyst agent."""
    
    config = BlueprintConfig(
        name="AnalystAgent",
        role="Data Analyst",
        capabilities=["data-analysis", "visualization", "insights"],
        system_prompt="""You are a Data Analyst expert at extracting insights from data.
Provide clear, actionable analysis with visualizations where helpful.""",
    )
    
    async def analyze(self, data: str) -> str:
        """Analyze data and provide insights."""
        return await self.invoke(f"Analyze the following data:\n\n{data}")


class WriterAgent(BlueprintAgent):
    """Creative writing agent."""
    
    config = BlueprintConfig(
        name="WriterAgent",
        role="Content Writer",
        capabilities=["writing", "editing", "content-creation"],
        temperature=0.8,
        system_prompt="""You are a creative Content Writer skilled at engaging content.
Write clear, compelling content tailored to the audience.""",
    )
    
    async def write(self, brief: str) -> str:
        """Write content based on a brief."""
        return await self.invoke(f"Write content based on:\n\n{brief}")


class ResearcherAgent(BlueprintAgent):
    """Research assistant agent."""
    
    config = BlueprintConfig(
        name="ResearcherAgent",
        role="Research Assistant",
        capabilities=["research", "summarization", "synthesis"],
        system_prompt="""You are a Research Assistant skilled at finding and synthesizing information.
Provide well-organized, cited research with clear conclusions.""",
    )
    
    async def research(self, topic: str) -> str:
        """Research a topic."""
        return await self.invoke(f"Research the following topic:\n\n{topic}")


# =============================================================================
# Blueprint Registry
# =============================================================================

BLUEPRINT_REGISTRY: Dict[str, Type[BlueprintAgent]] = {
    # SDLC Agents
    "requirements": RequirementsAgent,
    "design": DesignAgent,
    "development": DevelopmentAgent,
    "testing": TestingAgent,
    "security": SecurityAgent,
    "deployment": DeploymentAgent,
    "documentation": DocumentationAgent,
    "review": ReviewAgent,
    # Utility Agents
    "analyst": AnalystAgent,
    "writer": WriterAgent,
    "researcher": ResearcherAgent,
}


def get_blueprint(name: str, **kwargs) -> BlueprintAgent:
    """
    Get a blueprint agent by name.
    
    Args:
        name: Blueprint name
        **kwargs: Configuration overrides
        
    Returns:
        Blueprint agent instance
    """
    agent_class = BLUEPRINT_REGISTRY.get(name.lower())
    
    if agent_class is None:
        available = ", ".join(BLUEPRINT_REGISTRY.keys())
        raise ValueError(f"Unknown blueprint: {name}. Available: {available}")
    
    return agent_class(**kwargs)


def list_blueprints() -> List[str]:
    """List available blueprints."""
    return list(BLUEPRINT_REGISTRY.keys())
