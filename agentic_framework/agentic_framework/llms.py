"""
Agentic Framework LLMs Module

This module provides classes and utilities for integrating Large Language Models (LLMs) within the Agentic Framework.
LLMs are used to provide advanced reasoning, natural language understanding, and generation capabilities.
They enable agents to perform complex language-based tasks, from answering questions to generating detailed
reports, code, or creative content.

Key Features:
- LLM Integration: Connecting to various LLM providers through APIs or on-premise deployments.
- Model Selection and Switching: Choosing the most suitable model based on task requirements.
- Prompt Engineering: Crafting and optimizing prompts for improved output quality.
- Fine-Tuning and Customization: Adapting models to specific domains or tasks.
- Multi-Model Orchestration: Coordinating multiple LLMs for different subtasks.
- Context Management: Supplying relevant context and history for coherent responses.
- Output Validation: Checking generated outputs for accuracy and compliance.
- Performance Monitoring: Tracking latency, token usage, and quality metrics.
- Cost Optimization: Managing costs associated with LLM usage.
- Offline and Edge Deployment: Running LLMs locally for low-latency applications.
"""

from typing import Any, Dict, List, Optional, Callable, Set, Tuple
from datetime import datetime
import time
import threading
import uuid
import json
from abc import ABC, abstractmethod
from collections import deque, defaultdict

# Custom exceptions for LLMs
class LLMError(Exception):
    """Exception raised for errors related to LLM operations."""
    pass

class IntegrationError(LLMError):
    """Exception raised when LLM integration fails."""
    pass

class PromptError(LLMError):
    """Exception raised when prompt engineering or processing fails."""
    pass

class LLM(ABC):
    """
    Abstract base class for Large Language Models in the Agentic Framework.
    LLMs provide natural language understanding and generation capabilities.
    """
    def __init__(self, name: str, version: str = "1.0.0", description: str = "",
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize an LLM with basic metadata and configuration.
        
        Args:
            name (str): The name of the LLM.
            version (str): The version of the LLM (default: "1.0.0").
            description (str): A brief description of the LLM's purpose.
            config (Dict[str, Any], optional): Configuration parameters for the LLM.
        """
        self.name = name
        self.version = version
        self.description = description
        self.config = config or {}
        self.llm_id = str(uuid.uuid4())
        self.active = False
        self.last_used = 0.0
        self.usage_count = 0
        self.performance_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_latency": 0.0,
            "total_tokens_used": 0
        }
        self.usage_log = deque(maxlen=self.config.get("log_limit", 1000))
        self.lock = threading.Lock()

    @abstractmethod
    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a response based on the provided prompt and context.
        
        Args:
            prompt (str): The input prompt for the LLM.
            context (Dict[str, Any], optional): Additional contextual information for generation.
        
        Returns:
            Dict[str, Any]: Generated response with metadata.
        
        Raises:
            LLMError: If generation fails due to an error.
        """
        pass

    def activate(self) -> bool:
        """
        Activate the LLM for use.
        
        Returns:
            bool: True if activation was successful, False otherwise.
        """
        with self.lock:
            if not self.active:
                self.active = True
                self.last_used = time.time()
                return True
            return False

    def deactivate(self) -> bool:
        """
        Deactivate the LLM to prevent further use.
        
        Returns:
            bool: True if deactivation was successful, False otherwise.
        """
        with self.lock:
            if self.active:
                self.active = False
                return True
            return False

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        Update the LLM's configuration parameters.
        
        Args:
            new_config (Dict[str, Any]): The new configuration to apply.
        
        Returns:
            bool: True if the configuration update was successful.
        """
        with self.lock:
            self.config.update(new_config)
            return True

    def log_usage(self, usage_details: Dict[str, Any]) -> None:
        """
        Log an LLM usage event.
        
        Args:
            usage_details (Dict[str, Any]): Details of the usage event.
        """
        with self.lock:
            usage_details["timestamp"] = datetime.now().isoformat()
            usage_details["llm_name"] = self.name
            usage_details["llm_version"] = self.version
            self.usage_log.append(usage_details)
            self.usage_count += 1
            self.last_used = time.time()

    def _update_performance_metrics(self, start_time: float, end_time: float, success: bool, tokens_used: int = 0) -> None:
        """
        Update performance metrics based on generation results.
        
        Args:
            start_time (float): The start time of the generation.
            end_time (float): The end time of the generation.
            success (bool): Whether the generation was successful.
            tokens_used (int): Number of tokens used in the request.
        """
        with self.lock:
            latency = end_time - start_time
            self.performance_metrics["total_requests"] += 1
            if success:
                self.performance_metrics["successful_requests"] += 1
            else:
                self.performance_metrics["failed_requests"] += 1
            total_latency = self.performance_metrics["average_latency"] * (self.performance_metrics["total_requests"] - 1)
            self.performance_metrics["average_latency"] = (total_latency + latency) / self.performance_metrics["total_requests"]
            self.performance_metrics["total_tokens_used"] += tokens_used

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve monitoring data for this LLM.
        
        Returns:
            Dict[str, Any]: A dictionary containing monitoring metrics and status.
        """
        with self.lock:
            return {
                "llm_id": self.llm_id,
                "name": self.name,
                "version": self.version,
                "active": self.active,
                "description": self.description,
                "last_used": datetime.fromtimestamp(self.last_used).isoformat() if self.last_used > 0 else "Never",
                "usage_count": self.usage_count,
                "performance_metrics": self.performance_metrics.copy(),
                "recent_usage": list(self.usage_log)[-5:]  # Last 5 usage events
            }


class SimpleLLM(LLM):
    """
    A simple implementation of an LLM for testing or basic operations.
    """
    def __init__(self, name: str, version: str = "1.0.0", description: str = "Simple LLM",
                 config: Optional[Dict[str, Any]] = None,
                 generation_func: Optional[Callable[[str, Optional[Dict[str, Any]]], str]] = None):
        """
        Initialize a Simple LLM with an optional custom generation function.
        
        Args:
            name (str): The name of the LLM.
            version (str): The version of the LLM.
            description (str): A brief description of the LLM's purpose.
            config (Dict[str, Any], optional): Configuration parameters.
            generation_func (Callable, optional): Custom function for response generation.
        """
        super().__init__(name, version, description, config)
        self.generation_func = generation_func or (lambda p, ctx: f"Response to: {p}")

    def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a response based on the provided prompt.
        
        Args:
            prompt (str): The input prompt for the LLM.
            context (Dict[str, Any], optional): Additional contextual information.
        
        Returns:
            Dict[str, Any]: Generated response with metadata.
        """
        if not self.active:
            raise LLMError(f"Simple LLM {self.name} is not active")
        with self.lock:
            start_time = time.time()
            try:
                response_text = self.generation_func(prompt, context)
                end_time = time.time()
                tokens_used = len(prompt.split()) + len(response_text.split())  # Rough token estimate
                self._update_performance_metrics(start_time, end_time, success=True, tokens_used=tokens_used)
                response = {
                    "response_id": str(uuid.uuid4()),
                    "text": response_text,
                    "prompt": prompt[:100],  # Truncate long prompt
                    "metadata": {
                        "latency": end_time - start_time,
                        "tokens_used": tokens_used,
                        "model": self.name,
                        "version": self.version,
                        "context_used": bool(context)
                    }
                }
                self.log_usage({
                    "prompt": prompt[:100],
                    "response_length": len(response_text),
                    "success": True,
                    "context": context or {}
                })
                return response
            except Exception as e:
                end_time = time.time()
                self._update_performance_metrics(start_time, end_time, success=False)
                self.log_usage({
                    "prompt": prompt[:100],
                    "success": False,
                    "error": str(e),
                    "context": context or {}
                })
                raise LLMError(f"Error generating response with Simple LLM {self.name}: {str(e)}")


class LLMSelector:
    """
    Manages the selection and switching of LLMs based on task requirements, performance, and cost.
    """
    def __init__(self, name: str = "LLM Selector", config: Optional[Dict[str, Any]] = None):
        """
        Initialize the LLM Selector.
        
        Args:
            name (str): The name of the selector.
            config (Dict[str, Any], optional): Configuration parameters.
        """
        self.name = name
        self.config = config or {}
        self.llms: Dict[str, LLM] = {}
        self.llm_versions: Dict[str, List[str]] = defaultdict(list)
        self.selection_criteria = self.config.get("selection_criteria", {
            "task_type": {"weight": 0.4},
            "performance": {"weight": 0.3},
            "cost": {"weight": 0.2},
            "latency": {"weight": 0.1}
        })
        self.active = False
        self.selection_log = deque(maxlen=self.config.get("log_limit", 1000))
        self.last_selection = 0.0
        self.lock = threading.Lock()

    def activate(self) -> bool:
        """
        Activate the LLM Selector.
        
        Returns:
            bool: True if activation was successful.
        """
        with self.lock:
            if not self.active:
                self.active = True
                self.last_selection = time.time()
                self.selection_log.append(f"LLM Selector {self.name} activated at {datetime.now().isoformat()}")
            return True

    def deactivate(self) -> bool:
        """
        Deactivate the LLM Selector.
        
        Returns:
            bool: True if deactivation was successful.
        """
        with self.lock:
            if self.active:
                self.active = False
                self.selection_log.append(f"LLM Selector {self.name} deactivated at {datetime.now().isoformat()}")
            return True

    def register_llm(self, llm: LLM, overwrite: bool = False) -> bool:
        """
        Register a new LLM with the selector.
        
        Args:
            llm (LLM): The LLM to register.
            overwrite (bool): Whether to overwrite an existing LLM with the same name and version.
        
        Returns:
            bool: True if registration was successful.
        
        Raises:
            LLMError: If registration fails due to conflicts.
        """
        if not self.active:
            raise LLMError(f"LLM Selector {self.name} is not active")
        llm_key = f"{llm.name}:{llm.version}"
        with self.lock:
            if llm_key in self.llms and not overwrite:
                raise LLMError(f"LLM {llm.name} version {llm.version} already registered in selector {self.name}")
            self.llms[llm_key] = llm
            if llm.version not in self.llm_versions[llm.name]:
                self.llm_versions[llm.name].append(llm.version)
                self.llm_versions[llm.name].sort()
            self.selection_log.append(f"LLM {llm.name} version {llm.version} registered at {datetime.now().isoformat()}")
            self.last_selection = time.time()
            return True

    def select_llm(self, task_context: Dict[str, Any]) -> Optional[LLM]:
        """
        Select the most suitable LLM for the given task based on criteria.
        
        Args:
            task_context (Dict[str, Any]): Context about the task including type, requirements, etc.
        
        Returns:
            Optional[LLM]: The selected LLM, or None if no suitable LLM is found.
        """
        if not self.active:
            raise LLMError(f"LLM Selector {self.name} is not active")
        with self.lock:
            active_llms = [llm for llm in self.llms.values() if llm.active]
            if not active_llms:
                self.selection_log.append(f"No active LLMs available for selection at {datetime.now().isoformat()}")
                return None
            
            task_type = task_context.get("task_type", "general")
            best_llm = None
            best_score = -1.0
            
            for llm in active_llms:
                score = 0.0
                # Calculate score based on selection criteria
                for criterion, details in self.selection_criteria.items():
                    weight = details.get("weight", 0.1)
                    if criterion == "task_type":
                        supported_tasks = llm.config.get("supported_tasks", ["general"])
                        if task_type in supported_tasks:
                            score += weight * 1.0
                        else:
                            score += weight * 0.3  # Partial suitability
                    elif criterion == "performance":
                        success_rate = llm.performance_metrics.get("successful_requests", 0) / max(1, llm.performance_metrics.get("total_requests", 1))
                        score += weight * success_rate
                    elif criterion == "cost":
                        cost_per_token = llm.config.get("cost_per_token", 0.001)
                        normalized_cost = max(0.0, 1.0 - (cost_per_token / 0.01))  # Normalize cost impact
                        score += weight * normalized_cost
                    elif criterion == "latency":
                        avg_latency = llm.performance_metrics.get("average_latency", 1.0)
                        normalized_latency = max(0.0, 1.0 - (avg_latency / 5.0))  # Normalize latency impact
                        score += weight * normalized_latency
                
                if score > best_score:
                    best_score = score
                    best_llm = llm
            
            if best_llm:
                self.selection_log.append(f"Selected LLM {best_llm.name} (score: {best_score:.2f}) for task type {task_type} at {datetime.now().isoformat()}")
            else:
                self.selection_log.append(f"No suitable LLM selected for task type {task_type} at {datetime.now().isoformat()}")
            
            self.last_selection = time.time()
            return best_llm

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve monitoring data for the LLM Selector.
        
        Returns:
            Dict[str, Any]: A dictionary containing monitoring metrics and status.
        """
        with self.lock:
            llm_data = [llm.get_monitoring_data() for llm in self.llms.values()]
            return {
                "selector_name": self.name,
                "active": self.active,
                "total_llms": len(self.llms),
                "active_llms": sum(1 for llm in self.llms.values() if llm.active),
                "last_selection": datetime.fromtimestamp(self.last_selection).isoformat() if self.last_selection > 0 else "Never",
                "selection_log": list(self.selection_log)[-10:],  # Last 10 log entries
                "llms": llm_data
            }


class LLMPromptEngineer:
    """
    Manages the crafting and optimization of prompts for LLM interactions to improve output quality.
    """
    def __init__(self, name: str = "LLM Prompt Engineer", config: Optional[Dict[str, Any]] = None):
        """
        Initialize the LLM Prompt Engineer.
        
        Args:
            name (str): The name of the prompt engineer.
            config (Dict[str, Any], optional): Configuration parameters.
        """
        self.name = name
        self.config = config or {}
        self.prompt_templates = self.config.get("prompt_templates", {})
        self.optimization_strategies = self.config.get("optimization_strategies", {
            "clarity": lambda p: f"Answer clearly and concisely: {p}",
            "detail": lambda p: f"Provide a detailed and thorough response to: {p}",
            "step_by_step": lambda p: f"Explain step by step: {p}"
        })
        self.active = False
        self.prompt_log = deque(maxlen=self.config.get("log_limit", 1000))
        self.last_optimized = 0.0
        self.lock = threading.Lock()

    def activate(self) -> bool:
        """
        Activate the LLM Prompt Engineer.
        
        Returns:
            bool: True if activation was successful.
        """
        with self.lock:
            if not self.active:
                self.active = True
                self.last_optimized = time.time()
                self.prompt_log.append(f"LLM Prompt Engineer {self.name} activated at {datetime.now().isoformat()}")
            return True

    def deactivate(self) -> bool:
        """
        Deactivate the LLM Prompt Engineer.
        
        Returns:
            bool: True if deactivation was successful.
        """
        with self.lock:
            if self.active:
                self.active = False
                self.prompt_log.append(f"LLM Prompt Engineer {self.name} deactivated at {datetime.now().isoformat()}")
            return True

    def craft_prompt(self, base_prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Craft an optimized prompt based on the base input and context.
        
        Args:
            base_prompt (str): The base prompt or query to optimize.
            context (Dict[str, Any], optional): Additional contextual information for crafting.
        
        Returns:
            str: The crafted and optimized prompt.
        """
        if not self.active:
            return base_prompt  # Return unmodified if not active
        with self.lock:
            try:
                # Apply template if specified in context or config
                template_name = context.get("template", self.config.get("default_template", None)) if context else self.config.get("default_template", None)
                if template_name and template_name in self.prompt_templates:
                    template = self.prompt_templates[template_name]
                    crafted_prompt = template.format(prompt=base_prompt, **(context or {}))
                else:
                    crafted_prompt = base_prompt
                
                # Apply optimization strategies if specified
                strategies = context.get("strategies", self.config.get("default_strategies", [])) if context else self.config.get("default_strategies", [])
                for strategy in strategies:
                    if strategy in self.optimization_strategies:
                        crafted_prompt = self.optimization_strategies[strategy](crafted_prompt)
                
                # Add contextual data if provided
                if context and context.get("history"):
                    history_str = "\n".join([f"{entry['role']}: {entry['content']}" for entry in context.get("history", [])])
                    crafted_prompt = f"Conversation History:\n{history_str}\n\nCurrent Query: {crafted_prompt}"
                
                self.prompt_log.append({
                    "base_prompt": base_prompt[:100],  # Truncate long prompt
                    "crafted_prompt": crafted_prompt[:100],
                    "template_used": template_name or "None",
                    "strategies_applied": strategies,
                    "context": context or {}
                })
                self.last_optimized = time.time()
                return crafted_prompt
            except Exception as e:
                self.prompt_log.append({
                    "base_prompt": base_prompt[:100],
                    "error": str(e),
                    "context": context or {}
                })
                return base_prompt  # Return unmodified on error

    def update_templates(self, new_templates: Dict[str, str]) -> bool:
        """
        Update the prompt templates for crafting.
        
        Args:
            new_templates (Dict[str, str]): New prompt templates with placeholders.
        
        Returns:
            bool: True if update was successful.
        """
        with self.lock:
            self.prompt_templates.update(new_templates)
            return True

    def update_strategies(self, new_strategies: Dict[str, Callable[[str], str]]) -> bool:
        """
        Update the optimization strategies for prompt enhancement.
        
        Args:
            new_strategies (Dict[str, Callable[[str], str]]): New strategies as callable functions.
        
        Returns:
            bool: True if update was successful.
        """
        with self.lock:
            self.optimization_strategies.update(new_strategies)
            return True

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve monitoring data for the LLM Prompt Engineer.
        
        Returns:
            Dict[str, Any]: A dictionary containing monitoring metrics and status.
        """
        with self.lock:
            return {
                "engineer_name": self.name,
                "active": self.active,
                "last_optimized": datetime.fromtimestamp(self.last_optimized).isoformat() if self.last_optimized > 0 else "Never",
                "prompt_log": list(self.prompt_log)[-10:],  # Last 10 log entries
                "total_templates": len(self.prompt_templates),
                "total_strategies": len(self.optimization_strategies)
            }


class LLMManager:
    """
    Manages LLM operations within the Agentic Framework, coordinating model selection, prompt engineering,
    and response generation.
    """
    def __init__(self, name: str = "LLM Manager", config: Optional[Dict[str, Any]] = None):
        """
        Initialize the LLM Manager.
        
        Args:
            name (str): The name of the manager.
            config (Dict[str, Any], optional): Configuration parameters.
        """
        self.name = name
        self.config = config or {}
        self.llms: Dict[str, LLM] = {}
        self.llm_versions: Dict[str, List[str]] = defaultdict(list)
        self.selector = LLMSelector("DefaultSelector", config=self.config.get("selector_config", {}))
        self.prompt_engineer = LLMPromptEngineer("DefaultPromptEngineer", config=self.config.get("prompt_engineer_config", {}))
        self.active = False
        self.operation_log = deque(maxlen=self.config.get("log_limit", 1000))
        self.last_operation = 0.0
        self.lock = threading.Lock()

    def activate(self) -> bool:
        """
        Activate the LLM Manager, selector, prompt engineer, and all registered LLMs.
        
        Returns:
            bool: True if activation was successful.
        """
        with self.lock:
            if not self.active:
                self.active = True
                self.selector.activate()
                self.prompt_engineer.activate()
                for llm in self.llms.values():
                    llm.activate()
                self.last_operation = time.time()
                self.operation_log.append(f"LLM Manager {self.name} activated at {datetime.now().isoformat()}")
            return True

    def deactivate(self) -> bool:
        """
        Deactivate the LLM Manager, selector, prompt engineer, and all registered LLMs.
        
        Returns:
            bool: True if deactivation was successful.
        """
        with self.lock:
            if self.active:
                for llm in self.llms.values():
                    llm.deactivate()
                self.selector.deactivate()
                self.prompt_engineer.deactivate()
                self.active = False
                self.operation_log.append(f"LLM Manager {self.name} deactivated at {datetime.now().isoformat()}")
            return True

    def register_llm(self, llm: LLM, overwrite: bool = False) -> bool:
        """
        Register a new LLM with the manager and selector.
        
        Args:
            llm (LLM): The LLM to register.
            overwrite (bool): Whether to overwrite an existing LLM with the same name and version.
        
        Returns:
            bool: True if registration was successful.
        
        Raises:
            LLMError: If registration fails due to conflicts.
        """
        if not self.active:
            raise LLMError(f"LLM Manager {self.name} is not active")
        llm_key = f"{llm.name}:{llm.version}"
        with self.lock:
            if llm_key in self.llms and not overwrite:
                raise LLMError(f"LLM {llm.name} version {llm.version} already registered in manager {self.name}")
            self.llms[llm_key] = llm
            if llm.version not in self.llm_versions[llm.name]:
                self.llm_versions[llm.name].append(llm.version)
                self.llm_versions[llm.name].sort()
            self.selector.register_llm(llm, overwrite)
            if self.active:
                llm.activate()
            self.operation_log.append(f"LLM {llm.name} version {llm.version} registered at {datetime.now().isoformat()}")
            self.last_operation = time.time()
            return True

    def generate_response(self, prompt: str, context: Optional[Dict[str, Any]] = None,
                          llm_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a response using the specified or selected LLM.
        
        Args:
            prompt (str): The base prompt for generation.
            context (Dict[str, Any], optional): Additional contextual information for selection and generation.
            llm_name (str, optional): Specific LLM name to use. If None, select based on criteria.
        
        Returns:
            Dict[str, Any]: Generated response with metadata.
        """
        if not self.active:
            raise LLMError(f"LLM Manager {self.name} is not active")
        with self.lock:
            try:
                # Craft optimized prompt
                crafted_prompt = self.prompt_engineer.craft_prompt(prompt, context)
                
                # Select LLM if not specified
                if llm_name:
                    if llm_name in self.llm_versions:
                        latest_version = self.llm_versions[llm_name][-1]
                        llm_key = f"{llm_name}:{latest_version}"
                        selected_llm = self.llms.get(llm_key)
                        if not selected_llm or not selected_llm.active:
                            raise LLMError(f"Specified LLM {llm_name} is not active or not found")
                    else:
                        raise LLMError(f"Specified LLM {llm_name} not found in manager {self.name}")
                else:
                    selected_llm = self.selector.select_llm(context or {})
                    if not selected_llm:
                        raise LLMError(f"No suitable LLM selected for the given context")
                
                # Generate response using selected LLM
                response = selected_llm.generate(crafted_prompt, context)
                self.operation_log.append(f"Generated response with {selected_llm.name} for prompt {prompt[:50]} at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return response
            except LLMError as e:
                self.operation_log.append(f"Generation error: {str(e)} at {datetime.now().isoformat()}")
                raise
            except Exception as e:
                self.operation_log.append(f"Unexpected generation error: {str(e)} at {datetime.now().isoformat()}")
                raise LLMError(f"Unexpected error during response generation with {self.name}: {str(e)}")

    def update_llm_version(self, llm_name: str, old_version: str, new_version: str,
                           new_llm: Optional[LLM] = None) -> bool:
        """
        Update the version of an existing LLM or register a new LLM instance for the new version.
        
        Args:
            llm_name (str): The name of the LLM to update.
            old_version (str): The old version to replace or deprecate.
            new_version (str): The new version to introduce.
            new_llm (LLM, optional): A new LLM instance for the new version. If None, updates metadata only.
        
        Returns:
            bool: True if the version update was successful.
        """
        if not self.active:
            raise LLMError(f"LLM Manager {self.name} is not active")
        old_key = f"{llm_name}:{old_version}"
        new_key = f"{llm_name}:{new_version}"
        with self.lock:
            if old_key not in self.llms:
                raise LLMError(f"LLM {llm_name} version {old_version} not found in manager {self.name}")
            if new_key in self.llms:
                raise LLMError(f"LLM {llm_name} version {new_version} already exists in manager {self.name}")
            if new_llm:
                self.llms[new_key] = new_llm
                self.selector.register_llm(new_llm, overwrite=True)
            else:
                self.llms[new_key] = self.llms[old_key]
                self.llms[new_key].version = new_version
            if new_version not in self.llm_versions[llm_name]:
                self.llm_versions[llm_name].append(new_version)
                self.llm_versions[llm_name].sort()
            self.operation_log.append(f"LLM {llm_name} updated from version {old_version} to {new_version} at {datetime.now().isoformat()}")
            self.last_operation = time.time()
            return True

    def configure_llm(self, llm_name: str, llm_version: Optional[str] = None,
                      config: Dict[str, Any] = None) -> bool:
        """
        Configure an existing LLM with new settings.
        
        Args:
            llm_name (str): The name of the LLM to configure.
            llm_version (str, optional): The version of the LLM. If None, uses the latest.
            config (Dict[str, Any]): Configuration parameters to update.
        
        Returns:
            bool: True if configuration was successful.
        """
        if not self.active:
            return False
        with self.lock:
            if llm_name not in self.llm_versions:
                return False
            if llm_version is None:
                llm_version = self.llm_versions[llm_name][-1]
            llm_key = f"{llm_name}:{llm_version}"
            if llm_key not in self.llms:
                return False
            llm = self.llms[llm_key]
            if config:
                llm.update_config(config)
            self.operation_log.append(f"LLM {llm_name} version {llm_version} configured at {datetime.now().isoformat()}")
            self.last_operation = time.time()
            return True

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve comprehensive monitoring data for all managed LLMs and components.
        
        Returns:
            Dict[str, Any]: A dictionary containing monitoring metrics and status.
        """
        with self.lock:
            return {
                "manager_name": self.name,
                "active": self.active,
                "total_llms": len(self.llms),
                "active_llms": sum(1 for llm in self.llms.values() if llm.active),
                "last_operation": datetime.fromtimestamp(self.last_operation).isoformat() if self.last_operation > 0 else "Never",
                "operation_log": list(self.operation_log)[-10:],  # Last 10 log entries
                "selector_data": self.selector.get_monitoring_data(),
                "prompt_engineer_data": self.prompt_engineer.get_monitoring_data()
            }

    def multi_model_orchestration(self, prompt: str, context: Dict[str, Any], subtasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Coordinate multiple LLMs for different subtasks or fallback scenarios.
        
        Args:
            prompt (str): The base prompt for generation.
            context (Dict[str, Any]): Contextual information for orchestration.
            subtasks (List[Dict[str, Any]]): List of subtasks with specific LLM requirements or fallbacks.
        
        Returns:
            Dict[str, Any]: Combined results from orchestrated LLMs.
        """
        if not self.active:
            raise LLMError(f"LLM Manager {self.name} is not active for multi-model orchestration")
        with self.lock:
            try:
                orchestration_results = {
                    "timestamp": datetime.now().isoformat(),
                    "subtask_results": [],
                    "overall_result": ""
                }
                combined_text = []
                
                for subtask in subtasks:
                    subtask_context = subtask.get("context", context)
                    subtask_prompt = subtask.get("prompt", prompt)
                    llm_name = subtask.get("preferred_llm", None)
                    fallback_llms = subtask.get("fallback_llms", [])
                    
                    try:
                        response = self.generate_response(subtask_prompt, subtask_context, llm_name)
                        orchestration_results["subtask_results"].append({
                            "subtask": subtask.get("name", "unnamed_subtask"),
                            "llm_used": response.get("metadata", {}).get("model", "unknown"),
                            "success": True,
                            "response": response.get("text", ""),
                            "reason": "Primary LLM succeeded"
                        })
                        combined_text.append(response.get("text", ""))
                    except LLMError as e:
                        # Try fallback LLMs if primary fails
                        fallback_success = False
                        fallback_response = None
                        fallback_llm_used = None
                        
                        for fallback_llm in fallback_llms:
                            try:
                                fallback_response = self.generate_response(subtask_prompt, subtask_context, fallback_llm)
                                fallback_success = True
                                fallback_llm_used = fallback_llm
                                combined_text.append(fallback_response.get("text", ""))
                                break
                            except LLMError:
                                continue
                        
                        orchestration_results["subtask_results"].append({
                            "subtask": subtask.get("name", "unnamed_subtask"),
                            "llm_used": fallback_llm_used if fallback_success else llm_name,
                            "success": fallback_success,
                            "response": fallback_response.get("text", "") if fallback_success else str(e),
                            "reason": "Fallback succeeded" if fallback_success else "All LLMs failed"
                        })
                
                orchestration_results["overall_result"] = "\n".join(combined_text)
                self.operation_log.append(f"Multi-model orchestration completed with {len(subtasks)} subtasks at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return orchestration_results
            except Exception as e:
                self.operation_log.append(f"Multi-model orchestration error: {str(e)} at {datetime.now().isoformat()}")
                raise LLMError(f"Error during multi-model orchestration with {self.name}: {str(e)}")

    def cost_optimization(self, usage_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Manage and minimize costs associated with LLM usage through batching, caching, and model selection.
        
        Args:
            usage_data (Dict[str, Any]): Usage data to analyze for cost optimization.
        
        Returns:
            Dict[str, Any]: Optimization recommendations or actions taken.
        """
        if not self.active:
            return {"status": "LLM Manager not active, cost optimization not performed"}
        with self.lock:
            try:
                optimization_result = {
                    "timestamp": datetime.now().isoformat(),
                    "usage_summary": {
                        "total_requests": 0,
                        "total_tokens": 0,
                        "estimated_cost": 0.0
                    },
                    "recommendations": []
                }
                
                # Aggregate usage data from LLMs
                for llm in self.llms.values():
                    metrics = llm.performance_metrics
                    optimization_result["usage_summary"]["total_requests"] += metrics.get("total_requests", 0)
                    optimization_result["usage_summary"]["total_tokens"] += metrics.get("total_tokens_used", 0)
                    cost_per_token = llm.config.get("cost_per_token", 0.001)
                    optimization_result["usage_summary"]["estimated_cost"] += metrics.get("total_tokens_used", 0) * cost_per_token
                
                # Generate recommendations based on usage patterns
                if optimization_result["usage_summary"]["total_requests"] > self.config.get("high_usage_threshold", 1000):
                    optimization_result["recommendations"].append({
                        "type": "Model Selection",
                        "details": "Switch to lower-cost models for non-critical tasks to reduce expenses"
                    })
                
                if optimization_result["usage_summary"]["total_tokens"] > self.config.get("high_token_threshold", 1000000):
                    optimization_result["recommendations"].append({
                        "type": "Prompt Optimization",
                        "details": "Optimize prompts to reduce token usage for frequent queries"
                    })
                
                if "batching" in self.config.get("optimization_strategies", []):
                    optimization_result["recommendations"].append({
                        "type": "Batching",
                        "details": "Implement request batching to reduce API call overhead"
                    })
                
                self.operation_log.append(f"Cost optimization analysis completed at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return optimization_result
            except Exception as e:
                self.operation_log.append(f"Cost optimization error: {str(e)} at {datetime.now().isoformat()}")
                return {"error": str(e), "status": "Cost optimization failed"}

    def offline_deployment(self, llm_name: str, deployment_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deploy an LLM locally or on edge devices for low-latency, privacy-sensitive applications.
        
        Args:
            llm_name (str): The name of the LLM to deploy offline.
            deployment_config (Dict[str, Any]): Configuration for offline deployment.
        
        Returns:
            Dict[str, Any]: Deployment status and details.
        """
        if not self.active:
            return {"status": "LLM Manager not active, offline deployment not performed"}
        with self.lock:
            try:
                deployment_result = {
                    "timestamp": datetime.now().isoformat(),
                    "llm_name": llm_name,
                    "deployment_status": "Success",
                    "details": {}
                }
                
                if llm_name not in self.llm_versions:
                    raise LLMError(f"LLM {llm_name} not found in manager {self.name}")
                
                latest_version = self.llm_versions[llm_name][-1]
                llm_key = f"{llm_name}:{latest_version}"
                llm = self.llms.get(llm_key)
                
                if not llm:
                    raise LLMError(f"LLM {llm_name} version {latest_version} not found")
                
                # Placeholder for actual offline deployment logic
                # In a real system, this would handle model quantization, containerization, etc.
                deployment_result["details"] = {
                    "deployment_type": deployment_config.get("type", "local"),
                    "target_device": deployment_config.get("target_device", "edge_device"),
                    "model_size": deployment_config.get("model_size", "full"),
                    "message": f"Offline deployment of {llm_name} to {deployment_config.get('target_device', 'edge_device')} completed"
                }
                
                self.operation_log.append(f"Offline deployment of {llm_name} completed at {datetime.now().isoformat()}")
                self.last_operation = time.time()
                return deployment_result
            except LLMError as e:
                self.operation_log.append(f"Offline deployment error: {str(e)} at {datetime.now().isoformat()}")
                return {"status": "Failed", "error": str(e)}
            except Exception as e:
                self.operation_log.append(f"Unexpected offline deployment error: {str(e)} at {datetime.now().isoformat()}")
                return {"status": "Failed", "error": str(e)}


# Example usage and testing
if __name__ == "__main__":
    # Create an LLM manager
    llm_manager_config = {
        "log_limit": 100,
        "selector_config": {
            "selection_criteria": {
                "task_type": {"weight": 0.5},
                "performance": {"weight": 0.3},
                "cost": {"weight": 0.1},
                "latency": {"weight": 0.1}
            }
        },
        "prompt_engineer_config": {
            "prompt_templates": {
                "qa": "Question: {prompt}\nAnswer in a detailed and accurate manner.",
                "creative": "Write a creative piece about: {prompt}"
            },
            "default_strategies": ["clarity"],
            "optimization_strategies": {
                "clarity": lambda p: f"Answer clearly and concisely: {p}",
                "detail": lambda p: f"Provide a detailed and thorough response to: {p}",
                "step_by_step": lambda p: f"Explain step by step: {p}"
            }
        },
        "high_usage_threshold": 500,
        "high_token_threshold": 50000,
        "optimization_strategies": ["batching"]
    }
    llm_manager = LLMManager("TestLLMManager", config=llm_manager_config)
    llm_manager.activate()

    # Create and register LLMs
    simple_llm_1 = SimpleLLM("SimpleLLM1", config={
        "supported_tasks": ["general", "qa"],
        "cost_per_token": 0.001,
        "log_limit": 50
    }, generation_func=lambda p, ctx: f"SimpleLLM1 response to: {p}")
    simple_llm_2 = SimpleLLM("SimpleLLM2", config={
        "supported_tasks": ["creative", "coding"],
        "cost_per_token": 0.002,
        "log_limit": 50
    }, generation_func=lambda p, ctx: f"SimpleLLM2 creative response to: {p}")

    llm_manager.register_llm(simple_llm_1)
    llm_manager.register_llm(simple_llm_2)

    # Test response generation with automatic selection
    test_prompt = "Explain the concept of machine learning."
    context = {
        "task_type": "qa",
        "history": [
            {"role": "user", "content": "Tell me about AI."},
            {"role": "assistant", "content": "AI is a broad field..."}
        ],
        "template": "qa",
        "strategies": ["detail"]
    }
    try:
        response = llm_manager.generate_response(test_prompt, context)
        print(f"Generated Response (Auto-Selected LLM): {response['text']}")
        print(f"Metadata: {response['metadata']}")
    except LLMError as e:
        print(f"Generation Error: {e}")

    # Test response generation with specific LLM
    try:
        response = llm_manager.generate_response(test_prompt, context, llm_name="SimpleLLM2")
        print(f"Generated Response (Specific LLM - SimpleLLM2): {response['text']}")
        print(f"Metadata: {response['metadata']}")
    except LLMError as e:
        print(f"Generation Error with Specific LLM: {e}")

    # Test multi-model orchestration
    subtasks = [
        {"name": "Explain Concept", "prompt": test_prompt, "preferred_llm": "SimpleLLM1", "fallback_llms": ["SimpleLLM2"], "context": {"task_type": "qa"}},
        {"name": "Creative Example", "prompt": "Write a short story about AI.", "preferred_llm": "SimpleLLM2", "fallback_llms": ["SimpleLLM1"], "context": {"task_type": "creative"}}
    ]
    try:
        orchestration_result = llm_manager.multi_model_orchestration(test_prompt, context, subtasks)
        print(f"Multi-Model Orchestration Result:")
        for subtask_result in orchestration_result["subtask_results"]:
            print(f"- {subtask_result['subtask']} ({subtask_result['llm_used']}): {'Success' if subtask_result['success'] else 'Failed'}")
            print(f"  Response: {subtask_result['response'][:100]}...")
        print(f"Overall Result: {orchestration_result['overall_result'][:200]}...")
    except LLMError as e:
        print(f"Orchestration Error: {e}")

    # Test cost optimization
    usage_data = {
        "sample_requests": 600,
        "sample_tokens": 600000
    }
    cost_optimization_result = llm_manager.cost_optimization(usage_data)
    print(f"Cost Optimization Result: {cost_optimization_result}")

    # Test offline deployment
    deployment_config = {
        "type": "local",
        "target_device": "edge_device",
        "model_size": "quantized"
    }
    try:
        deployment_result = llm_manager.offline_deployment("SimpleLLM1", deployment_config)
        print(f"Offline Deployment Result: {deployment_result}")
    except LLMError as e:
        print(f"Deployment Error: {e}")

    # Get monitoring data
    monitoring_data = llm_manager.get_monitoring_data()
    print(f"LLM Manager Monitoring Data: {json.dumps(monitoring_data, indent=2)[:500]}... (truncated)")
