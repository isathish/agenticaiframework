"""
Enterprise SDLC Pipeline - Complete SDLC automation with minimal code.

Pre-built SDLC pipeline that handles requirements, design, development,
testing, security, and deployment with a single function call.

Usage:
    >>> from agenticaiframework.enterprise import create_sdlc_pipeline
    >>> 
    >>> # One-liner SDLC
    >>> pipeline = create_sdlc_pipeline("my-project", model="gpt-4o")
    >>> result = await pipeline.run("Build an e-commerce API")
    >>> 
    >>> for phase, artifact in result.artifacts.items():
    ...     print(f"{phase}: {len(artifact)} chars")
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

logger = logging.getLogger(__name__)


# =============================================================================
# SDLC Types
# =============================================================================

class SDLCPhase(Enum):
    """SDLC phases."""
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    DEVELOPMENT = "development"
    TESTING = "testing"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    DOCUMENTATION = "documentation"
    REVIEW = "review"


@dataclass
class SDLCArtifact:
    """Artifact produced by an SDLC phase."""
    phase: SDLCPhase
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    version: str = "1.0"
    
    def to_dict(self) -> Dict:
        return {
            "phase": self.phase.value,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
        }


@dataclass
class SDLCConfig:
    """Configuration for SDLC pipeline."""
    project_name: str
    description: str = ""
    phases: List[str] = field(default_factory=lambda: [
        "requirements", "design", "development", "testing", "security", "deployment", "documentation"
    ])
    model: str = "gpt-4o"
    provider: str = "azure"
    enable_storage: bool = True
    enable_tracing: bool = True
    output_dir: str = "artifacts"
    parallel_phases: bool = False


@dataclass
class SDLCResult:
    """Result from SDLC pipeline execution."""
    success: bool
    project_name: str
    phases_completed: List[str]
    artifacts: Dict[str, str]
    errors: Dict[str, str] = field(default_factory=dict)
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def summary(self) -> str:
        """Get execution summary."""
        status = "✅ SUCCESS" if self.success else "❌ FAILED"
        lines = [
            f"\n{'='*60}",
            f"SDLC PIPELINE RESULT: {status}",
            f"{'='*60}",
            f"Project: {self.project_name}",
            f"Duration: {self.duration_seconds:.2f}s",
            f"Phases: {len(self.phases_completed)}/{len(self.phases_completed) + len(self.errors)}",
            f"{'='*60}",
        ]
        
        for phase in self.phases_completed:
            artifact_len = len(self.artifacts.get(phase, ""))
            lines.append(f"  ✓ {phase}: {artifact_len} chars")
        
        for phase, error in self.errors.items():
            lines.append(f"  ✗ {phase}: {error[:50]}...")
        
        lines.append(f"{'='*60}\n")
        return "\n".join(lines)


# =============================================================================
# Phase Prompts
# =============================================================================

PHASE_PROMPTS = {
    "requirements": """You are a Requirements Analyst.
Analyze the following project description and create detailed software requirements.

Include:
1. Functional Requirements (FR-001, FR-002, etc.)
2. Non-Functional Requirements (NFR-001, etc.)
3. User Stories with acceptance criteria
4. Priority levels (Must Have, Should Have, Nice to Have)
5. Dependencies and constraints

Project: {project_name}
Description: {description}

{context}

Provide comprehensive, structured requirements in markdown format.""",

    "design": """You are a Software Architect.
Based on the following requirements, create a comprehensive technical design.

Include:
1. System Architecture (with component diagram description)
2. Database Design (tables, relationships, indexes)
3. API Design (endpoints, methods, request/response schemas)
4. Technology Stack recommendations
5. Security considerations
6. Scalability approach

Project: {project_name}
Requirements:
{previous_output}

{context}

Provide a detailed technical design document in markdown format.""",

    "development": """You are a Senior Software Developer.
Based on the following design, implement the core code.

Include:
1. Complete, production-ready code
2. Proper error handling
3. Logging and monitoring hooks
4. Configuration management
5. Database models and migrations
6. API implementation
7. Unit test stubs

Project: {project_name}
Design:
{previous_output}

{context}

Provide clean, well-documented, production-quality code.""",

    "testing": """You are a QA Engineer.
Create a comprehensive test strategy and test cases for this project.

Include:
1. Test Strategy document
2. Unit test cases with expected results
3. Integration test scenarios
4. Performance test plan
5. Security test checklist
6. UAT test cases

Project: {project_name}
Code/Design:
{previous_output}

{context}

Provide detailed test documentation in markdown format.""",

    "security": """You are a Security Analyst.
Perform a security analysis and provide recommendations.

Include:
1. Threat Model (STRIDE analysis)
2. Vulnerability Assessment
3. Security Requirements
4. Authentication/Authorization review
5. Data protection recommendations
6. Security testing checklist
7. Compliance considerations (GDPR, SOC2, etc.)

Project: {project_name}
Implementation:
{previous_output}

{context}

Provide a comprehensive security analysis report.""",

    "deployment": """You are a DevOps Engineer.
Create deployment configuration and infrastructure code.

Include:
1. Dockerfile and docker-compose
2. Kubernetes manifests (if applicable)
3. CI/CD pipeline configuration
4. Infrastructure as Code (Terraform/Bicep)
5. Environment configuration
6. Monitoring and alerting setup
7. Rollback procedures

Project: {project_name}
Application:
{previous_output}

{context}

Provide complete deployment configuration files.""",

    "documentation": """You are a Technical Writer.
Create comprehensive project documentation.

Include:
1. README.md with setup instructions
2. API documentation
3. Architecture documentation
4. User guide
5. Developer guide
6. Operations runbook
7. Troubleshooting guide

Project: {project_name}
Project Details:
{previous_output}

{context}

Provide complete, user-friendly documentation in markdown format.""",

    "review": """You are a Senior Code Reviewer.
Review all project artifacts and provide feedback.

Include:
1. Code quality assessment
2. Best practices compliance
3. Security review findings
4. Performance considerations
5. Improvement recommendations
6. Final approval status

Project: {project_name}
All Artifacts:
{previous_output}

{context}

Provide a comprehensive review report with actionable feedback.""",
}


# =============================================================================
# SDLC Pipeline
# =============================================================================

class SDLCPipeline:
    """
    Complete SDLC pipeline with pre-configured agents for each phase.
    
    Usage:
        >>> pipeline = SDLCPipeline(
        ...     project_name="my-project",
        ...     description="Build an e-commerce API",
        ... )
        >>> result = await pipeline.run()
        >>> print(result.summary())
    """
    
    def __init__(
        self,
        project_name: str,
        description: str = "",
        *,
        phases: Optional[List[str]] = None,
        model: str = "gpt-4o",
        provider: str = "azure",
        enable_storage: bool = True,
        enable_tracing: bool = True,
        output_dir: str = "artifacts",
        **kwargs,
    ):
        self.config = SDLCConfig(
            project_name=project_name,
            description=description,
            phases=phases or [
                "requirements", "design", "development", 
                "testing", "security", "deployment", "documentation"
            ],
            model=model,
            provider=provider,
            enable_storage=enable_storage,
            enable_tracing=enable_tracing,
            output_dir=output_dir,
        )
        
        self.artifacts: Dict[str, SDLCArtifact] = {}
        self._llm_client = None
        self._adapter = None
    
    def _get_llm_client(self):
        """Get or create LLM client."""
        if self._llm_client is None:
            if self.config.provider == "azure":
                try:
                    from openai import AzureOpenAI
                    self._llm_client = AzureOpenAI(
                        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                        api_version="2024-02-01",
                    )
                except ImportError:
                    raise ImportError("openai is required. Install with: pip install openai")
            else:
                # Fallback to adapters
                from .adapters import get_adapter
                self._adapter = get_adapter(self.config.provider)
        
        return self._llm_client
    
    async def _call_llm(self, prompt: str) -> str:
        """Call LLM with appropriate parameters."""
        client = self._get_llm_client()
        
        if client:
            messages = [{"role": "user", "content": prompt}]
            
            params = {
                "model": self.config.model,
                "messages": messages,
            }
            
            # Handle model-specific parameters
            if "gpt-5" in self.config.model.lower():
                params["max_completion_tokens"] = 16384
                params["temperature"] = 1
            else:
                params["max_tokens"] = 16384
                params["temperature"] = 0.7
            
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(**params)
            )
            
            return response.choices[0].message.content
        elif self._adapter:
            return await self._adapter.llm.generate(prompt)
        else:
            raise RuntimeError("No LLM client available")
    
    async def run(
        self,
        description: Optional[str] = None,
        *,
        context: str = "",
        save_artifacts: bool = True,
        verbose: bool = True,
    ) -> SDLCResult:
        """
        Run the complete SDLC pipeline.
        
        Args:
            description: Override project description
            context: Additional context for all phases
            save_artifacts: Save artifacts to disk
            verbose: Print progress
            
        Returns:
            SDLCResult with all artifacts and status
        """
        start_time = datetime.now()
        
        project_desc = description or self.config.description
        phases_completed = []
        artifacts = {}
        errors = {}
        
        previous_output = ""
        
        if verbose:
            print(f"\n{'='*60}", flush=True)
            print(f"🚀 STARTING SDLC PIPELINE: {self.config.project_name}", flush=True)
            print(f"{'='*60}", flush=True)
            print(f"Phases: {', '.join(self.config.phases)}", flush=True)
            print(f"Model: {self.config.model}", flush=True)
            print(f"{'='*60}\n", flush=True)
        
        for phase in self.config.phases:
            if verbose:
                print(f"\n📋 Phase: {phase.upper()}", flush=True)
                print(f"{'-'*40}", flush=True)
            
            try:
                # Get phase prompt
                prompt_template = PHASE_PROMPTS.get(
                    phase, 
                    f"Process the {phase} phase for project {{project_name}}. Context: {{previous_output}}"
                )
                
                prompt = prompt_template.format(
                    project_name=self.config.project_name,
                    description=project_desc,
                    previous_output=previous_output[:10000],  # Limit context size
                    context=context,
                )
                
                if verbose:
                    print(f"  Generating {phase} output...", flush=True)
                
                # Call LLM
                output = await self._call_llm(prompt)
                
                # Store artifact
                artifact = SDLCArtifact(
                    phase=SDLCPhase(phase) if phase in [p.value for p in SDLCPhase] else SDLCPhase.REVIEW,
                    content=output,
                    metadata={"model": self.config.model, "project": self.config.project_name},
                )
                
                self.artifacts[phase] = artifact
                artifacts[phase] = output
                phases_completed.append(phase)
                previous_output = output
                
                if verbose:
                    print(f"  ✓ {phase} complete: {len(output)} chars", flush=True)
                
                # Save to disk if enabled
                if save_artifacts and self.config.enable_storage:
                    await self._save_artifact(phase, output)
                
            except Exception as e:
                error_msg = str(e)
                errors[phase] = error_msg
                
                if verbose:
                    print(f"  ✗ {phase} failed: {error_msg[:100]}", flush=True)
                
                logger.error(f"Phase {phase} failed: {e}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        result = SDLCResult(
            success=len(errors) == 0,
            project_name=self.config.project_name,
            phases_completed=phases_completed,
            artifacts=artifacts,
            errors=errors,
            duration_seconds=duration,
        )
        
        if verbose:
            print(result.summary(), flush=True)
        
        return result
    
    async def _save_artifact(self, phase: str, content: str):
        """Save artifact to disk."""
        output_dir = self.config.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{self.config.project_name}_{phase}.md"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w") as f:
            f.write(f"# {self.config.project_name} - {phase.title()}\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write(f"---\n\n")
            f.write(content)
        
        logger.info(f"Saved artifact: {filepath}")
    
    async def run_phase(
        self,
        phase: str,
        *,
        input_data: str = "",
        context: str = "",
    ) -> SDLCArtifact:
        """
        Run a single SDLC phase.
        
        Args:
            phase: Phase name
            input_data: Input from previous phase
            context: Additional context
            
        Returns:
            SDLCArtifact
        """
        prompt_template = PHASE_PROMPTS.get(phase, f"Process {phase} for {{project_name}}")
        
        prompt = prompt_template.format(
            project_name=self.config.project_name,
            description=self.config.description,
            previous_output=input_data,
            context=context,
        )
        
        output = await self._call_llm(prompt)
        
        artifact = SDLCArtifact(
            phase=SDLCPhase(phase) if phase in [p.value for p in SDLCPhase] else SDLCPhase.REVIEW,
            content=output,
            metadata={"model": self.config.model},
        )
        
        self.artifacts[phase] = artifact
        return artifact
    
    def get_artifact(self, phase: str) -> Optional[SDLCArtifact]:
        """Get artifact for a phase."""
        return self.artifacts.get(phase)
    
    def export_all(self, output_dir: Optional[str] = None) -> str:
        """Export all artifacts to a directory."""
        output_dir = output_dir or self.config.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        for phase, artifact in self.artifacts.items():
            filename = f"{self.config.project_name}_{phase}.md"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, "w") as f:
                f.write(artifact.content)
        
        return output_dir


# =============================================================================
# Convenience Function
# =============================================================================

def create_sdlc_pipeline(
    project: str,
    description: str = "",
    **kwargs,
) -> SDLCPipeline:
    """
    Create an SDLC pipeline with one line.
    
    Args:
        project: Project name
        description: Project description
        **kwargs: Additional SDLCPipeline configuration
        
    Returns:
        Configured SDLCPipeline
        
    Example:
        >>> pipeline = create_sdlc_pipeline(
        ...     "my-app",
        ...     "Build a REST API for user management",
        ...     model="gpt-4o",
        ... )
        >>> result = await pipeline.run()
    """
    return SDLCPipeline(
        project_name=project,
        description=description,
        **kwargs,
    )
