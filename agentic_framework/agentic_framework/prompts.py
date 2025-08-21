"""
Prompts Module for Agentic Framework SDK

This module provides functionality for creating and managing prompts, which are structured inputs
that guide agent behavior by defining context, instructions, and constraints.
"""

from typing import List, Dict, Any, Optional
import time

class PromptError(Exception):
    """Exception raised for errors related to prompt operations."""
    pass

class Prompt:
    """
    Base class for a prompt in the Agentic Framework.
    Prompts define the context and instructions for agents to perform tasks effectively.
    """
    def __init__(self, name: str, content: str, template: bool = False, version: str = "1.0.0",
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a prompt with a name, content, and metadata.
        
        Args:
            name (str): The unique identifier for the prompt.
            content (str): The content or text of the prompt.
            template (bool, optional): Whether this prompt is a template with placeholders.
            version (str, optional): Version of the prompt for tracking and updates.
            metadata (Dict[str, Any], optional): Additional metadata for discovery and categorization.
        """
        self.name = name
        self.content = content
        self.template = template
        self.version = version
        self.metadata = metadata or {}
        self.creation_time = time.time()
        self.last_updated = self.creation_time

    def update_content(self, new_content: str) -> str:
        """
        Update the content of the prompt.
        
        Args:
            new_content (str): The new content for the prompt.
            
        Returns:
            str: Result of the update operation.
        """
        self.content = new_content
        self.last_updated = time.time()
        return f"Prompt {self.name} updated with new content"

    def update_version(self, new_version: str) -> str:
        """
        Update the version of the prompt.
        
        Args:
            new_version (str): New version string.
            
        Returns:
            str: Result of the operation.
        """
        old_version = self.version
        self.version = new_version
        self.last_updated = time.time()
        return f"Prompt {self.name} updated from version {old_version} to {new_version}"

    def generate(self, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate the final prompt text, filling in placeholders if it's a template.
        
        Args:
            params (Dict[str, Any], optional): Dictionary of placeholder values to fill in the template.
            
        Returns:
            str: The final prompt text.
        """
        if self.template and params:
            try:
                return self.content.format(**params)
            except KeyError as e:
                return f"Error in prompt generation for {self.name}: Missing parameter {e}"
        return self.content

    def add_context(self, context_data: Dict[str, Any]) -> str:
        """
        Add contextual data to the prompt content.
        
        Args:
            context_data (Dict[str, Any]): Contextual data to incorporate into the prompt.
            
        Returns:
            str: Result of the operation.
        """
        context_str = "\n".join([f"{key}: {value}" for key, value in context_data.items()])
        self.content = f"{self.content}\nContext:\n{context_str}"
        self.last_updated = time.time()
        return f"Context added to prompt {self.name}"

class PromptTemplate:
    """
    Class for managing reusable prompt templates with placeholders in the Agentic Framework.
    Allows for dynamic prompt generation by filling in placeholders with values.
    """
    def __init__(self, name: str, structure: str, version: str = "1.0.0",
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a prompt template with a name and structure.
        
        Args:
            name (str): The unique identifier for the prompt template.
            structure (str): The template structure with placeholders (e.g., "{variable}").
            version (str, optional): Version of the template for tracking and updates.
            metadata (Dict[str, Any], optional): Additional metadata for discovery and categorization.
        """
        self.name = name
        self.structure = structure
        self.version = version
        self.metadata = metadata or {}
        self.creation_time = time.time()
        self.last_updated = self.creation_time

    def set_structure(self, new_structure: str) -> str:
        """
        Update the structure of the template.
        
        Args:
            new_structure (str): New template structure with placeholders.
            
        Returns:
            str: Result of the operation.
        """
        self.structure = new_structure
        self.last_updated = time.time()
        return f"Template structure updated for {self.name}"

    def update_version(self, new_version: str) -> str:
        """
        Update the version of the template.
        
        Args:
            new_version (str): New version string.
            
        Returns:
            str: Result of the operation.
        """
        old_version = self.version
        self.version = new_version
        self.last_updated = time.time()
        return f"Template {self.name} updated from version {old_version} to {new_version}"

    def generate(self, params: Dict[str, Any]) -> str:
        """
        Generate a prompt by filling in the template placeholders with provided values.
        
        Args:
            params (Dict[str, Any]): Dictionary of placeholder values to fill in the template.
            
        Returns:
            str: Generated prompt text or error message if parameters are missing.
        """
        try:
            return self.structure.format(**params)
        except KeyError as e:
            return f"Error generating prompt {self.name}: Missing parameter {e}"

class PromptChain:
    """
    Class for chaining multiple prompts together in the Agentic Framework.
    Guides agents through multi-step reasoning or workflows using a sequence of prompts.
    """
    def __init__(self, name: str, active: bool = True, version: str = "1.0.0"):
        """
        Initialize a prompt chain with a name, activation status, and version.
        
        Args:
            name (str): The unique identifier for the prompt chain.
            active (bool, optional): Whether the prompt chain is active by default. Defaults to True.
            version (str, optional): Version of the prompt chain for tracking.
        """
        self.name = name
        self.active = active
        self.version = version
        self.prompts: List[Any] = []
        self.creation_time = time.time()
        self.last_updated = self.creation_time

    def add_prompt(self, prompt: Any) -> str:
        """
        Add a prompt to the chain.
        
        Args:
            prompt (Prompt or PromptTemplate): The prompt or template to add to the chain.
            
        Returns:
            str: Result of the addition operation.
        """
        if not self.active:
            return f"Prompt Chain {self.name} is not active"
        self.prompts.append(prompt)
        self.last_updated = time.time()
        return f"Prompt {prompt.name} added to chain {self.name}"

    def remove_prompt(self, prompt_name: str) -> str:
        """
        Remove a prompt from the chain by name.
        
        Args:
            prompt_name (str): Name of the prompt to remove.
            
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Prompt Chain {self.name} is not active"
        for i, prompt in enumerate(self.prompts):
            if prompt.name == prompt_name:
                self.prompts.pop(i)
                self.last_updated = time.time()
                return f"Prompt {prompt_name} removed from chain {self.name}"
        return f"Prompt {prompt_name} not found in chain {self.name}"

    def execute(self, params_list: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """
        Execute the sequence of prompts in the chain, filling in templates if necessary.
        
        Args:
            params_list (List[Dict[str, Any]], optional): List of parameter dictionaries for template prompts.
            
        Returns:
            List[str]: List of generated prompt texts or error message if not active.
        """
        if not self.active:
            return [f"Prompt Chain {self.name} is not active"]
        if params_list and len(params_list) != len(self.prompts):
            return [f"Error: Mismatch in params_list length for chain {self.name}"]
        
        results = []
        for i, prompt in enumerate(self.prompts):
            if isinstance(prompt, PromptTemplate):
                params = params_list[i] if params_list else {}
                results.append(prompt.generate(params))
            else:
                results.append(prompt.generate())
        return results

    def update_version(self, new_version: str) -> str:
        """
        Update the version of the prompt chain.
        
        Args:
            new_version (str): New version string.
            
        Returns:
            str: Result of the operation.
        """
        old_version = self.version
        self.version = new_version
        self.last_updated = time.time()
        return f"Prompt Chain {self.name} updated from version {old_version} to {new_version}"

class PromptManager:
    """
    Manager class for handling prompts and templates in the Agentic Framework.
    Provides functionality for prompt discovery, versioning, and optimization.
    """
    def __init__(self, name: str, active: bool = True):
        """
        Initialize a prompt manager with a name and activation status.
        
        Args:
            name (str): The unique identifier for the prompt manager.
            active (bool, optional): Whether the manager is active by default. Defaults to True.
        """
        self.name = name
        self.active = active
        self.prompts: Dict[str, Any] = {}
        self.discovery_metadata: Dict[str, Dict[str, Any]] = {}

    def add_prompt(self, prompt: Any, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a prompt or template to the manager's registry.
        
        Args:
            prompt (Prompt or PromptTemplate): The prompt or template to add.
            metadata (Dict[str, Any], optional): Additional metadata for discovery and categorization.
            
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Prompt Manager {self.name} is not active"
        self.prompts[prompt.name] = prompt
        if metadata:
            self.discovery_metadata[prompt.name] = metadata
        else:
            self.discovery_metadata[prompt.name] = {
                "version": prompt.version,
                "type": "template" if isinstance(prompt, PromptTemplate) else "prompt",
                "use_case": "general"
            }
        return f"Prompt {prompt.name} added to manager {self.name} with metadata"

    def remove_prompt(self, prompt_name: str) -> str:
        """
        Remove a prompt from the manager's registry.
        
        Args:
            prompt_name (str): Name of the prompt to remove.
            
        Returns:
            str: Result of the operation.
        """
        if not self.active:
            return f"Prompt Manager {self.name} is not active"
        if prompt_name in self.prompts:
            self.prompts.pop(prompt_name)
            self.discovery_metadata.pop(prompt_name, None)
            return f"Prompt {prompt_name} removed from manager {self.name}"
        return f"Prompt {prompt_name} not found in manager {self.name}"

    def discover_prompts(self, criteria: Optional[Dict[str, Any]] = None) -> List[Any]:
        """
        Discover prompts based on specific criteria such as use case or type.
        
        Args:
            criteria (Dict[str, Any], optional): Criteria to filter prompts (e.g., {"use_case": "conversation"}).
            
        Returns:
            List[Any]: List of matching prompts or templates.
        """
        if not self.active:
            return []
        if not criteria:
            return list(self.prompts.values())
        
        matching_prompts = []
        for prompt_name, metadata in self.discovery_metadata.items():
            matches_all_criteria = True
            for key, value in criteria.items():
                if key in metadata:
                    if metadata[key] != value:
                        matches_all_criteria = False
                        break
                else:
                    matches_all_criteria = False
                    break
            if matches_all_criteria:
                matching_prompts.append(self.prompts[prompt_name])
        return matching_prompts

    def get_prompt(self, prompt_name: str) -> Optional[Any]:
        """
        Retrieve a specific prompt by name.
        
        Args:
            prompt_name (str): Name of the prompt to retrieve.
            
        Returns:
            Optional[Any]: The prompt or template if found, None otherwise.
        """
        if not self.active:
            return None
        return self.prompts.get(prompt_name)

    def optimize_prompt(self, prompt_name: str, optimization_goal: str) -> str:
        """
        Optimize a prompt for a specific goal such as clarity or brevity.
        
        Args:
            prompt_name (str): Name of the prompt to optimize.
            optimization_goal (str): The goal of optimization (e.g., "clarity", "brevity").
            
        Returns:
            str: Result of the optimization operation.
        """
        if not self.active:
            return f"Prompt Manager {self.name} is not active"
        if prompt_name not in self.prompts:
            return f"Prompt {prompt_name} not found in manager {self.name}"
        # Placeholder for optimization logic
        return f"Prompt {prompt_name} optimized for {optimization_goal}"

    def validate_prompt(self, prompt_name: str, guardrails: Optional[Dict[str, Any]] = None) -> str:
        """
        Validate a prompt against specified guardrails or default constraints.
        
        Args:
            prompt_name (str): Name of the prompt to validate.
            guardrails (Dict[str, Any], optional): Guardrail constraints to validate against.
            
        Returns:
            str: Result of the validation operation.
        """
        if not self.active:
            return f"Prompt Manager {self.name} is not active"
        if prompt_name not in self.prompts:
            return f"Prompt {prompt_name} not found in manager {self.name}"
        prompt = self.prompts[prompt_name]
        # Basic validation logic
        if not prompt.content:
            return f"Validation failed for prompt {prompt_name}: Empty content"
        if guardrails:
            for key, constraint in guardrails.items():
                if key == "max_length" and len(prompt.content) > constraint:
                    return f"Validation failed for prompt {prompt_name}: Content exceeds max length {constraint}"
        return f"Prompt {prompt_name} validated successfully"

    def generate_dynamic_prompt(self, base_prompt_name: str, context_data: Dict[str, Any],
                                params: Optional[Dict[str, Any]] = None) -> str:
        """
        Dynamically generate a prompt based on a base prompt and contextual data.
        
        Args:
            base_prompt_name (str): Name of the base prompt or template to use.
            context_data (Dict[str, Any]): Contextual data to incorporate into the prompt.
            params (Dict[str, Any], optional): Parameters for template placeholders.
            
        Returns:
            str: Generated dynamic prompt text.
        """
        if not self.active:
            return f"Prompt Manager {self.name} is not active"
        if base_prompt_name not in self.prompts:
            return f"Base prompt {base_prompt_name} not found in manager {self.name}"
        base_prompt = self.prompts[base_prompt_name]
        if isinstance(base_prompt, PromptTemplate):
            return base_prompt.generate(params or {})
        else:
            context_str = "\n".join([f"{key}: {value}" for key, value in context_data.items()])
            return f"{base_prompt.content}\nDynamic Context:\n{context_str}"

    def coordinate_multi_agent_prompts(self, prompt_chain_name: str, agent_names: List[str],
                                       params_list: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """
        Coordinate prompts for multiple agents using a prompt chain.
        
        Args:
            prompt_chain_name (str): Name of the prompt chain to use.
            agent_names (List[str]): List of agent names to coordinate prompts for.
            params_list (List[Dict[str, Any]], optional): List of parameter dictionaries for templates.
            
        Returns:
            List[str]: List of generated prompts for each agent.
        """
        if not self.active:
            return [f"Prompt Manager {self.name} is not active"]
        if prompt_chain_name not in self.prompts:
            return [f"Prompt chain {prompt_chain_name} not found in manager {self.name}"]
        chain = self.prompts[prompt_chain_name]
        if not isinstance(chain, PromptChain):
            return [f"Prompt {prompt_chain_name} is not a PromptChain"]
        if len(agent_names) != len(chain.prompts):
            return [f"Error: Mismatch between agent count ({len(agent_names)}) and prompt count ({len(chain.prompts)})"]
        results = chain.execute(params_list)
        return [f"Prompt for agent {agent}: {result}" for agent, result in zip(agent_names, results)]
