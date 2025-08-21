"""
Agentic Framework Guardrails Module

This module provides classes and utilities for implementing guardrails within the Agentic Framework.
Guardrails are safety, compliance, and quality control mechanisms that ensure agents operate within
defined boundaries and adhere to organizational, legal, and ethical standards. They prevent undesired
behaviors, enforce constraints, and maintain trust in agentic operations.

Key Features:
- Guardrails Discovery: Identifying and managing guardrail configurations.
- Input and Output Validation: Ensuring data meets predefined formats and safety checks.
- Streaming Output Validation: Validating outputs in real-time as they are generated.
- Policy Enforcement: Applying organizational, legal, or ethical policies to agent actions.
- Content Filtering: Detecting and removing sensitive or harmful content.
- Rate Limiting and Quotas: Controlling frequency and volume of agent actions.
- Contextual Guardrails: Adjusting constraints based on task or environment.
- Fallback and Recovery Mechanisms: Switching to safe actions on violations.
- Guardrail Versioning: Managing different versions of guardrails.
- Guardrail Monitoring: Tracking activations, violations, and effectiveness.
"""

from typing import Any, Dict, List, Optional, Callable, Set, Tuple
from datetime import datetime
import time
import threading
import uuid
import json
import re
from abc import ABC, abstractmethod
from collections import deque, defaultdict

# Custom exceptions for Guardrails
class GuardrailError(Exception):
    """Exception raised for errors related to guardrail operations."""
    pass

class ValidationError(GuardrailError):
    """Exception raised when validation fails."""
    pass

class PolicyViolationError(GuardrailError):
    """Exception raised when a policy is violated."""
    pass

class RateLimitError(GuardrailError):
    """Exception raised when rate limits or quotas are exceeded."""
    pass

class Guardrail(ABC):
    """
    Abstract base class for guardrails in the Agentic Framework.
    Guardrails define constraints and safety mechanisms for agent operations.
    """
    def __init__(self, name: str, version: str = "1.0.0", description: str = "",
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize a Guardrail with basic metadata and configuration.
        
        Args:
            name (str): The name of the guardrail.
            version (str): The version of the guardrail (default: "1.0.0").
            description (str): A brief description of the guardrail's purpose.
            config (Dict[str, Any], optional): Configuration parameters for the guardrail.
        """
        self.name = name
        self.version = version
        self.description = description
        self.config = config or {}
        self.guardrail_id = str(uuid.uuid4())
        self.active = False
        self.last_triggered = 0.0
        self.trigger_count = 0
        self.violation_log = deque(maxlen=self.config.get("log_limit", 1000))
        self.lock = threading.Lock()

    @abstractmethod
    def enforce(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Enforce the guardrail on the provided input data.
        
        Args:
            input_data (Any): The data to check against the guardrail.
            context (Dict[str, Any], optional): Additional contextual information.
        
        Returns:
            bool: True if the data passes the guardrail, False if a violation occurs.
        
        Raises:
            GuardrailError: If enforcement fails due to an error.
        """
        pass

    def activate(self) -> bool:
        """
        Activate the guardrail for enforcement.
        
        Returns:
            bool: True if activation was successful, False otherwise.
        """
        with self.lock:
            if not self.active:
                self.active = True
                self.last_triggered = time.time()
                return True
            return False

    def deactivate(self) -> bool:
        """
        Deactivate the guardrail to stop enforcement.
        
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
        Update the guardrail's configuration parameters.
        
        Args:
            new_config (Dict[str, Any]): The new configuration to apply.
        
        Returns:
            bool: True if the configuration update was successful.
        """
        with self.lock:
            self.config.update(new_config)
            return True

    def log_violation(self, violation_details: Dict[str, Any]) -> None:
        """
        Log a guardrail violation.
        
        Args:
            violation_details (Dict[str, Any]): Details of the violation.
        """
        with self.lock:
            violation_details["timestamp"] = datetime.now().isoformat()
            violation_details["guardrail_name"] = self.name
            violation_details["guardrail_version"] = self.version
            self.violation_log.append(violation_details)
            self.trigger_count += 1
            self.last_triggered = time.time()

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve monitoring data for this guardrail.
        
        Returns:
            Dict[str, Any]: A dictionary containing monitoring metrics and status.
        """
        with self.lock:
            return {
                "guardrail_id": self.guardrail_id,
                "name": self.name,
                "version": self.version,
                "active": self.active,
                "description": self.description,
                "last_triggered": datetime.fromtimestamp(self.last_triggered).isoformat() if self.last_triggered > 0 else "Never",
                "trigger_count": self.trigger_count,
                "recent_violations": list(self.violation_log)[-5:]  # Last 5 violations
            }


class ValidationGuardrail(Guardrail):
    """
    A guardrail for validating input and output data against predefined formats and constraints.
    """
    def __init__(self, name: str, version: str = "1.0.0", description: str = "Validation Guardrail",
                 config: Optional[Dict[str, Any]] = None,
                 validation_rules: Optional[Dict[str, Callable[[Any], bool]]] = None):
        """
        Initialize a Validation Guardrail.
        
        Args:
            name (str): The name of the guardrail.
            version (str): The version of the guardrail.
            description (str): A brief description of the guardrail's purpose.
            config (Dict[str, Any], optional): Configuration parameters.
            validation_rules (Dict[str, Callable], optional): Custom validation rules as callable functions.
        """
        super().__init__(name, version, description, config)
        self.validation_rules = validation_rules or {}
        self.default_rules = {
            "not_none": lambda x: x is not None,
            "string_not_empty": lambda x: isinstance(x, str) and len(x.strip()) > 0,
            "list_not_empty": lambda x: isinstance(x, (list, tuple)) and len(x) > 0,
            "positive_number": lambda x: isinstance(x, (int, float)) and x > 0
        }
        self.rules = {**self.default_rules, **self.validation_rules}

    def enforce(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Enforce validation rules on the input data.
        
        Args:
            input_data (Any): The data to validate.
            context (Dict[str, Any], optional): Additional contextual information with rule specifications.
        
        Returns:
            bool: True if validation passes, False if a violation occurs.
        
        Raises:
            ValidationError: If validation fails critically.
        """
        if not self.active:
            return True  # Guardrail not active, pass through
        with self.lock:
            try:
                rules_to_apply = context.get("validation_rules", self.config.get("default_rules", [])) if context else self.config.get("default_rules", [])
                if not rules_to_apply:  # If no specific rules, apply all available
                    rules_to_apply = list(self.rules.keys())
                violations = []
                for rule_name in rules_to_apply:
                    if rule_name in self.rules:
                        if not self.rules[rule_name](input_data):
                            violations.append({
                                "rule_name": rule_name,
                                "data": str(input_data)[:100],  # Truncate long data
                                "reason": f"Failed validation rule: {rule_name}"
                            })
                if violations:
                    self.log_violation({
                        "type": "Validation Failure",
                        "violations": violations,
                        "context": context or {}
                    })
                    return False
                return True
            except Exception as e:
                self.log_violation({
                    "type": "Validation Error",
                    "error": str(e),
                    "data": str(input_data)[:100],
                    "context": context or {}
                })
                raise ValidationError(f"Error enforcing validation guardrail {self.name}: {str(e)}")

    def add_validation_rule(self, rule_name: str, rule_func: Callable[[Any], bool]) -> bool:
        """
        Add a new validation rule to the guardrail.
        
        Args:
            rule_name (str): The name of the new rule.
            rule_func (Callable): The function to validate data, returning True if valid.
        
        Returns:
            bool: True if the rule was added successfully.
        """
        with self.lock:
            self.rules[rule_name] = rule_func
            return True


class PolicyEnforcer(Guardrail):
    """
    A guardrail for enforcing organizational, legal, or ethical policies on agent actions and outputs.
    """
    def __init__(self, name: str, version: str = "1.0.0", description: str = "Policy Enforcer Guardrail",
                 config: Optional[Dict[str, Any]] = None,
                 policies: Optional[Dict[str, Callable[[Any, Dict[str, Any]], bool]]] = None):
        """
        Initialize a Policy Enforcer Guardrail.
        
        Args:
            name (str): The name of the guardrail.
            version (str): The version of the guardrail.
            description (str): A brief description of the guardrail's purpose.
            config (Dict[str, Any], optional): Configuration parameters.
            policies (Dict[str, Callable], optional): Policy functions to enforce.
        """
        super().__init__(name, version, description, config)
        self.policies = policies or {}
        self.default_policies = {
            "no_profanity": self._check_no_profanity,
            "content_length_limit": self._check_content_length_limit
        }
        self.policy_functions = {**self.default_policies, **self.policies}

    def _check_no_profanity(self, data: Any, context: Dict[str, Any]) -> bool:
        """
        Default policy to check for profanity in text data.
        
        Args:
            data (Any): The data to check.
            context (Dict[str, Any]): Contextual information.
        
        Returns:
            bool: True if no profanity is detected, False otherwise.
        """
        if not isinstance(data, str):
            return True
        profanity_list = self.config.get("profanity_list", [])
        if not profanity_list:
            return True
        data_lower = data.lower()
        for word in profanity_list:
            if word.lower() in data_lower:
                return False
        return True

    def _check_content_length_limit(self, data: Any, context: Dict[str, Any]) -> bool:
        """
        Default policy to enforce content length limits.
        
        Args:
            data (Any): The data to check.
            context (Dict[str, Any]): Contextual information with possible custom limits.
        
        Returns:
            bool: True if within limits, False otherwise.
        """
        max_length = context.get("max_length", self.config.get("max_content_length", 10000))
        if isinstance(data, str):
            return len(data) <= max_length
        elif isinstance(data, (list, tuple)):
            return len(data) <= max_length
        elif isinstance(data, dict):
            return len(json.dumps(data)) <= max_length
        return True

    def enforce(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Enforce policy rules on the input data.
        
        Args:
            input_data (Any): The data to check against policies.
            context (Dict[str, Any], optional): Additional contextual information.
        
        Returns:
            bool: True if all policies are satisfied, False if a violation occurs.
        
        Raises:
            PolicyViolationError: If policy enforcement fails critically.
        """
        if not self.active:
            return True  # Guardrail not active, pass through
        with self.lock:
            try:
                policies_to_apply = context.get("policies", self.config.get("default_policies", [])) if context else self.config.get("default_policies", [])
                if not policies_to_apply:  # If no specific policies, apply all available
                    policies_to_apply = list(self.policy_functions.keys())
                violations = []
                for policy_name in policies_to_apply:
                    if policy_name in self.policy_functions:
                        if not self.policy_functions[policy_name](input_data, context or {}):
                            violations.append({
                                "policy_name": policy_name,
                                "data": str(input_data)[:100],  # Truncate long data
                                "reason": f"Violated policy: {policy_name}"
                            })
                if violations:
                    self.log_violation({
                        "type": "Policy Violation",
                        "violations": violations,
                        "context": context or {}
                    })
                    return False
                return True
            except Exception as e:
                self.log_violation({
                    "type": "Policy Enforcement Error",
                    "error": str(e),
                    "data": str(input_data)[:100],
                    "context": context or {}
                })
                raise PolicyViolationError(f"Error enforcing policy guardrail {self.name}: {str(e)}")

    def add_policy(self, policy_name: str, policy_func: Callable[[Any, Dict[str, Any]], bool]) -> bool:
        """
        Add a new policy to the guardrail.
        
        Args:
            policy_name (str): The name of the new policy.
            policy_func (Callable): The function to enforce the policy, returning True if compliant.
        
        Returns:
            bool: True if the policy was added successfully.
        """
        with self.lock:
            self.policy_functions[policy_name] = policy_func
            return True


class ContentFilter(Guardrail):
    """
    A guardrail for filtering content to detect and remove sensitive, harmful, or prohibited material.
    """
    def __init__(self, name: str, version: str = "1.0.0", description: str = "Content Filter Guardrail",
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize a Content Filter Guardrail.
        
        Args:
            name (str): The name of the guardrail.
            version (str): The version of the guardrail.
            description (str): A brief description of the guardrail's purpose.
            config (Dict[str, Any], optional): Configuration parameters.
        """
        super().__init__(name, version, description, config)
        self.blocked_patterns = self.config.get("blocked_patterns", [])
        self.blocked_words = self.config.get("blocked_words", [])
        self.sensitive_data_regex = self.config.get("sensitive_data_regex", [
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN pattern
            r"\b(?:\d[ -]*?){13,16}\b"  # Credit card pattern
        ])
        self.replacement_text = self.config.get("replacement_text", "[REDACTED]")

    def enforce(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Enforce content filtering on the input data.
        
        Args:
            input_data (Any): The data to filter (typically text).
            context (Dict[str, Any], optional): Additional contextual information.
        
        Returns:
            bool: True if content passes filtering (or is filtered successfully), False if a critical violation occurs.
        """
        if not self.active:
            return True  # Guardrail not active, pass through
        with self.lock:
            try:
                if not isinstance(input_data, str):
                    return True  # Non-string data passes through
                violations = []
                filtered_content = input_data

                # Check for blocked words
                for word in self.blocked_words:
                    if word.lower() in input_data.lower():
                        violations.append({
                            "type": "Blocked Word",
                            "word": word,
                            "reason": f"Content contains blocked word: {word}"
                        })
                        filtered_content = re.sub(re.escape(word), self.replacement_text, filtered_content, flags=re.IGNORECASE)

                # Check for blocked patterns
                for pattern in self.blocked_patterns:
                    if re.search(pattern, input_data, re.IGNORECASE):
                        violations.append({
                            "type": "Blocked Pattern",
                            "pattern": pattern,
                            "reason": f"Content matches blocked pattern: {pattern}"
                        })
                        filtered_content = re.sub(pattern, self.replacement_text, filtered_content, flags=re.IGNORECASE)

                # Check for sensitive data patterns
                for regex in self.sensitive_data_regex:
                    if re.search(regex, input_data):
                        violations.append({
                            "type": "Sensitive Data",
                            "pattern": regex,
                            "reason": "Content contains sensitive data pattern"
                        })
                        filtered_content = re.sub(regex, self.replacement_text, filtered_content)

                if violations:
                    self.log_violation({
                        "type": "Content Filter Violation",
                        "violations": violations,
                        "original_content": input_data[:100],  # Truncate long content
                        "filtered_content": filtered_content[:100],
                        "context": context or {}
                    })
                    # Depending on config, either block or allow filtered content
                    if self.config.get("block_on_violation", True):
                        return False
                    else:
                        # If not blocking, the filtered content would be used downstream
                        # For simplicity, we just return False to indicate a violation occurred
                        return False
                return True
            except Exception as e:
                self.log_violation({
                    "type": "Content Filter Error",
                    "error": str(e),
                    "data": str(input_data)[:100],
                    "context": context or {}
                })
                raise GuardrailError(f"Error enforcing content filter guardrail {self.name}: {str(e)}")

    def update_filters(self, blocked_words: Optional[List[str]] = None,
                       blocked_patterns: Optional[List[str]] = None,
                       sensitive_data_regex: Optional[List[str]] = None) -> bool:
        """
        Update the content filters with new lists of blocked content or patterns.
        
        Args:
            blocked_words (List[str], optional): New list of blocked words.
            blocked_patterns (List[str], optional): New list of blocked patterns.
            sensitive_data_regex (List[str], optional): New list of sensitive data regex patterns.
        
        Returns:
            bool: True if update was successful.
        """
        with self.lock:
            if blocked_words is not None:
                self.blocked_words = blocked_words
            if blocked_patterns is not None:
                self.blocked_patterns = blocked_patterns
            if sensitive_data_regex is not None:
                self.sensitive_data_regex = sensitive_data_regex
            return True


class RateLimiter(Guardrail):
    """
    A guardrail for enforcing rate limits and quotas on agent actions to prevent abuse or overload.
    """
    def __init__(self, name: str, version: str = "1.0.0", description: str = "Rate Limiter Guardrail",
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize a Rate Limiter Guardrail.
        
        Args:
            name (str): The name of the guardrail.
            version (str): The version of the guardrail.
            description (str): A brief description of the guardrail's purpose.
            config (Dict[str, Any], optional): Configuration parameters including rate limits.
        """
        super().__init__(name, version, description, config)
        self.rate_limit = self.config.get("rate_limit", 10)  # actions per window
        self.window_size = self.config.get("window_size", 60.0)  # seconds
        self.action_history = defaultdict(deque)  # Track actions per entity
        self.quota_limit = self.config.get("quota_limit", 100)  # Total actions allowed in larger period
        self.quota_period = self.config.get("quota_period", 3600.0)  # Quota reset period in seconds
        self.quota_usage = defaultdict(float)  # Track quota usage per entity
        self.quota_reset_time = defaultdict(float)  # Track when quota resets per entity

    def enforce(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Enforce rate limiting and quotas based on the context (e.g., agent ID, user ID).
        
        Args:
            input_data (Any): The data or action to rate limit (often irrelevant for rate limiting).
            context (Dict[str, Any], optional): Contextual information including entity identifier.
        
        Returns:
            bool: True if within rate limits and quotas, False if exceeded.
        
        Raises:
            RateLimitError: If rate limiting fails critically.
        """
        if not self.active:
            return True  # Guardrail not active, pass through
        with self.lock:
            try:
                entity_id = context.get("entity_id", "default_entity") if context else "default_entity"
                current_time = time.time()

                # Reset quota if period has passed
                if self.quota_reset_time[entity_id] == 0.0 or current_time - self.quota_reset_time[entity_id] >= self.quota_period:
                    self.quota_usage[entity_id] = 0.0
                    self.quota_reset_time[entity_id] = current_time

                # Check quota first
                if self.quota_usage[entity_id] >= self.quota_limit:
                    self.log_violation({
                        "type": "Quota Exceeded",
                        "entity_id": entity_id,
                        "quota_usage": self.quota_usage[entity_id],
                        "quota_limit": self.quota_limit,
                        "context": context or {}
                    })
                    return False

                # Clean up old actions outside the current window
                while self.action_history[entity_id] and current_time - self.action_history[entity_id][0] > self.window_size:
                    self.action_history[entity_id].popleft()

                # Check rate limit
                if len(self.action_history[entity_id]) >= self.rate_limit:
                    self.log_violation({
                        "type": "Rate Limit Exceeded",
                        "entity_id": entity_id,
                        "action_count": len(self.action_history[entity_id]),
                        "rate_limit": self.rate_limit,
                        "window_size": self.window_size,
                        "context": context or {}
                    })
                    return False

                # Record the action
                self.action_history[entity_id].append(current_time)
                self.quota_usage[entity_id] += 1
                return True
            except Exception as e:
                self.log_violation({
                    "type": "Rate Limiter Error",
                    "error": str(e),
                    "context": context or {}
                })
                raise RateLimitError(f"Error enforcing rate limiter guardrail {self.name}: {str(e)}")

    def update_limits(self, rate_limit: Optional[int] = None, window_size: Optional[float] = None,
                      quota_limit: Optional[int] = None, quota_period: Optional[float] = None) -> bool:
        """
        Update rate limiting and quota parameters.
        
        Args:
            rate_limit (int, optional): New rate limit (actions per window).
            window_size (float, optional): New window size in seconds.
            quota_limit (int, optional): New total quota limit.
            quota_period (float, optional): New quota reset period in seconds.
        
        Returns:
            bool: True if update was successful.
        """
        with self.lock:
            if rate_limit is not None:
                self.rate_limit = rate_limit
            if window_size is not None:
                self.window_size = window_size
            if quota_limit is not None:
                self.quota_limit = quota_limit
            if quota_period is not None:
                self.quota_period = quota_period
            return True

    def get_rate_limit_status(self, entity_id: str) -> Dict[str, Any]:
        """
        Retrieve the current rate limit and quota status for an entity.
        
        Args:
            entity_id (str): The identifier of the entity to check.
        
        Returns:
            Dict[str, Any]: Current rate limit and quota usage information.
        """
        with self.lock:
            current_time = time.time()
            # Clean up old actions
            while self.action_history[entity_id] and current_time - self.action_history[entity_id][0] > self.window_size:
                self.action_history[entity_id].popleft()
            # Check if quota needs reset
            if self.quota_reset_time[entity_id] == 0.0 or current_time - self.quota_reset_time[entity_id] >= self.quota_period:
                self.quota_usage[entity_id] = 0.0
                self.quota_reset_time[entity_id] = current_time
            return {
                "entity_id": entity_id,
                "current_rate": len(self.action_history[entity_id]),
                "rate_limit": self.rate_limit,
                "window_size": self.window_size,
                "quota_usage": self.quota_usage[entity_id],
                "quota_limit": self.quota_limit,
                "quota_period": self.quota_period,
                "quota_reset_time": datetime.fromtimestamp(self.quota_reset_time[entity_id]).isoformat() if self.quota_reset_time[entity_id] > 0 else "Never"
            }


class GuardrailManager:
    """
    Manages guardrails within the Agentic Framework, coordinating their enforcement,
    discovery, versioning, and monitoring.
    """
    def __init__(self, name: str = "Guardrail Manager", config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Guardrail Manager.
        
        Args:
            name (str): The name of the manager.
            config (Dict[str, Any], optional): Configuration parameters.
        """
        self.name = name
        self.config = config or {}
        self.guardrails: Dict[str, Guardrail] = {}
        self.guardrail_versions: Dict[str, List[str]] = defaultdict(list)
        self.active = False
        self.enforcement_log = deque(maxlen=self.config.get("log_limit", 1000))
        self.last_enforcement = 0.0
        self.lock = threading.Lock()

    def activate(self) -> bool:
        """
        Activate the Guardrail Manager and all registered guardrails.
        
        Returns:
            bool: True if activation was successful.
        """
        with self.lock:
            if not self.active:
                self.active = True
                for guardrail in self.guardrails.values():
                    guardrail.activate()
                self.last_enforcement = time.time()
                self.enforcement_log.append(f"Guardrail Manager {self.name} activated at {datetime.now().isoformat()}")
            return True

    def deactivate(self) -> bool:
        """
        Deactivate the Guardrail Manager and all registered guardrails.
        
        Returns:
            bool: True if deactivation was successful.
        """
        with self.lock:
            if self.active:
                for guardrail in self.guardrails.values():
                    guardrail.deactivate()
                self.active = False
                self.enforcement_log.append(f"Guardrail Manager {self.name} deactivated at {datetime.now().isoformat()}")
            return True

    def register_guardrail(self, guardrail: Guardrail, overwrite: bool = False) -> bool:
        """
        Register a new guardrail with the manager.
        
        Args:
            guardrail (Guardrail): The guardrail to register.
            overwrite (bool): Whether to overwrite an existing guardrail with the same name and version.
        
        Returns:
            bool: True if registration was successful.
        
        Raises:
            GuardrailError: If registration fails due to conflicts.
        """
        if not self.active:
            raise GuardrailError(f"Guardrail Manager {self.name} is not active")
        guardrail_key = f"{guardrail.name}:{guardrail.version}"
        with self.lock:
            if guardrail_key in self.guardrails and not overwrite:
                raise GuardrailError(f"Guardrail {guardrail.name} version {guardrail.version} already registered in manager {self.name}")
            self.guardrails[guardrail_key] = guardrail
            if guardrail.version not in self.guardrail_versions[guardrail.name]:
                self.guardrail_versions[guardrail.name].append(guardrail.version)
                self.guardrail_versions[guardrail.name].sort()
            if self.active:
                guardrail.activate()
            self.enforcement_log.append(f"Guardrail {guardrail.name} version {guardrail.version} registered at {datetime.now().isoformat()}")
            self.last_enforcement = time.time()
            return True

    def discover_guardrails(self, criteria: Optional[Dict[str, Any]] = None) -> List[Guardrail]:
        """
        Discover available guardrails based on optional criteria.
        
        Args:
            criteria (Dict[str, Any], optional): Criteria to filter guardrails (e.g., name, version, active status).
        
        Returns:
            List[Guardrail]: List of matching guardrails.
        """
        if not self.active:
            return []
        with self.lock:
            if not criteria:
                return list(self.guardrails.values())
            matching_guardrails = []
            for guardrail in self.guardrails.values():
                matches = True
                for key, value in criteria.items():
                    if key == "name" and guardrail.name != value:
                        matches = False
                    elif key == "version" and guardrail.version != value:
                        matches = False
                    elif key == "active" and guardrail.active != value:
                        matches = False
                if matches:
                    matching_guardrails.append(guardrail)
            return matching_guardrails

    def enforce_guardrails(self, input_data: Any, context: Optional[Dict[str, Any]] = None,
                           guardrail_names: Optional[List[str]] = None) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Enforce specified or all active guardrails on the input data.
        
        Args:
            input_data (Any): The data to check against guardrails.
            context (Dict[str, Any], optional): Additional contextual information.
            guardrail_names (List[str], optional): Specific guardrail names to enforce. If None, enforce all active.
        
        Returns:
            Tuple[bool, List[Dict[str, Any]]]: A tuple of (success_status, list_of_violation_details).
            success_status is True if all guardrails pass, False if any fail.
            list_of_violation_details contains details of any violations.
        """
        if not self.active:
            return True, [{"manager": self.name, "status": "Not active, guardrails not enforced"}]
        with self.lock:
            violations = []
            success = True
            target_guardrails = []
            if guardrail_names:
                for name in guardrail_names:
                    if name in self.guardrail_versions:
                        latest_version = self.guardrail_versions[name][-1]
                        key = f"{name}:{latest_version}"
                        if key in self.guardrails and self.guardrails[key].active:
                            target_guardrails.append(self.guardrails[key])
            else:
                target_guardrails = [g for g in self.guardrails.values() if g.active]

            for guardrail in target_guardrails:
                try:
                    if not guardrail.enforce(input_data, context):
                        success = False
                        violation_data = guardrail.get_monitoring_data()
                        violations.append({
                            "guardrail_name": guardrail.name,
                            "version": guardrail.version,
                            "violation_details": violation_data.get("recent_violations", []),
                            "reason": f"Guardrail {guardrail.name} enforcement failed"
                        })
                except GuardrailError as e:
                    success = False
                    violations.append({
                        "guardrail_name": guardrail.name,
                        "version": guardrail.version,
                        "error": str(e),
                        "reason": f"Error enforcing guardrail {guardrail.name}"
                    })
                    self.enforcement_log.append(f"Error enforcing guardrail {guardrail.name}: {str(e)} at {datetime.now().isoformat()}")

            if violations:
                self.enforcement_log.append(f"Guardrail violations detected: {len(violations)} violations at {datetime.now().isoformat()}")
            self.last_enforcement = time.time()
            return success, violations

    def update_guardrail_version(self, guardrail_name: str, old_version: str, new_version: str,
                                 new_guardrail: Optional[Guardrail] = None) -> bool:
        """
        Update the version of an existing guardrail or register a new guardrail instance for the new version.
        
        Args:
            guardrail_name (str): The name of the guardrail to update.
            old_version (str): The old version to replace or deprecate.
            new_version (str): The new version to introduce.
            new_guardrail (Guardrail, optional): A new guardrail instance for the new version. If None, updates metadata only.
        
        Returns:
            bool: True if the version update was successful.
        """
        if not self.active:
            raise GuardrailError(f"Guardrail Manager {self.name} is not active")
        old_key = f"{guardrail_name}:{old_version}"
        new_key = f"{guardrail_name}:{new_version}"
        with self.lock:
            if old_key not in self.guardrails:
                raise GuardrailError(f"Guardrail {guardrail_name} version {old_version} not found in manager {self.name}")
            if new_key in self.guardrails:
                raise GuardrailError(f"Guardrail {guardrail_name} version {new_version} already exists in manager {self.name}")
            if new_guardrail:
                self.guardrails[new_key] = new_guardrail
            else:
                self.guardrails[new_key] = self.guardrails[old_key]
                self.guardrails[new_key].version = new_version
            if new_version not in self.guardrail_versions[guardrail_name]:
                self.guardrail_versions[guardrail_name].append(new_version)
                self.guardrail_versions[guardrail_name].sort()
            self.enforcement_log.append(f"Guardrail {guardrail_name} updated from version {old_version} to {new_version} at {datetime.now().isoformat()}")
            self.last_enforcement = time.time()
            return True

    def configure_guardrail(self, guardrail_name: str, guardrail_version: Optional[str] = None,
                            config: Dict[str, Any] = None) -> bool:
        """
        Configure an existing guardrail with new settings.
        
        Args:
            guardrail_name (str): The name of the guardrail to configure.
            guardrail_version (str, optional): The version of the guardrail. If None, uses the latest.
            config (Dict[str, Any]): Configuration parameters to update.
        
        Returns:
            bool: True if configuration was successful.
        """
        if not self.active:
            return False
        with self.lock:
            if guardrail_name not in self.guardrail_versions:
                return False
            if guardrail_version is None:
                guardrail_version = self.guardrail_versions[guardrail_name][-1]
            guardrail_key = f"{guardrail_name}:{guardrail_version}"
            if guardrail_key not in self.guardrails:
                return False
            guardrail = self.guardrails[guardrail_key]
            if config:
                guardrail.update_config(config)
            self.enforcement_log.append(f"Guardrail {guardrail_name} version {guardrail_version} configured at {datetime.now().isoformat()}")
            self.last_enforcement = time.time()
            return True

    def get_monitoring_data(self) -> Dict[str, Any]:
        """
        Retrieve comprehensive monitoring data for all managed guardrails.
        
        Returns:
            Dict[str, Any]: A dictionary containing monitoring metrics and status for the manager and guardrails.
        """
        with self.lock:
            guardrail_data = [guardrail.get_monitoring_data() for guardrail in self.guardrails.values()]
            return {
                "manager_name": self.name,
                "active": self.active,
                "total_guardrails": len(self.guardrails),
                "active_guardrails": sum(1 for guardrail in self.guardrails.values() if guardrail.active),
                "last_enforcement": datetime.fromtimestamp(self.last_enforcement).isoformat() if self.last_enforcement > 0 else "Never",
                "enforcement_log": list(self.enforcement_log)[-10:],  # Last 10 log entries
                "guardrails": guardrail_data
            }

    def apply_contextual_guardrails(self, input_data: Any, context: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Apply guardrails dynamically based on the current context, task, or environment.
        
        Args:
            input_data (Any): The data to check against contextual guardrails.
            context (Dict[str, Any]): Contextual information to determine applicable guardrails.
        
        Returns:
            Tuple[bool, List[Dict[str, Any]]]: A tuple of (success_status, list_of_violation_details).
        """
        if not self.active:
            return True, [{"manager": self.name, "status": "Not active, contextual guardrails not enforced"}]
        with self.lock:
            # Determine applicable guardrails based on context
            task_type = context.get("task_type", "default")
            environment = context.get("environment", "production")
            user_role = context.get("user_role", "user")
            applicable_guardrails = []
            for guardrail in self.guardrails.values():
                if not guardrail.active:
                    continue
                guardrail_config = guardrail.config
                applies_to_task = guardrail_config.get("applies_to_tasks", []) == [] or task_type in guardrail_config.get("applies_to_tasks", [])
                applies_to_env = guardrail_config.get("applies_to_environments", []) == [] or environment in guardrail_config.get("applies_to_environments", [])
                applies_to_role = guardrail_config.get("applies_to_roles", []) == [] or user_role in guardrail_config.get("applies_to_roles", [])
                if applies_to_task and applies_to_env and applies_to_role:
                    applicable_guardrails.append(guardrail.name)
            return self.enforce_guardrails(input_data, context, applicable_guardrails)

    def fallback_recovery(self, violation_details: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Implement fallback and recovery mechanisms when guardrail violations occur.
        
        Args:
            violation_details (List[Dict[str, Any]]): Details of the violations that occurred.
            context (Dict[str, Any], optional): Additional contextual information.
        
        Returns:
            Dict[str, Any]: Recovery action details or fallback instructions.
        """
        if not self.active:
            return {"status": "Guardrail manager not active, no fallback applied"}
        with self.lock:
            recovery_action = {
                "status": "Fallback applied",
                "violations": violation_details,
                "fallback_action": self.config.get("default_fallback", "block_action"),
                "timestamp": datetime.now().isoformat()
            }
            if context and context.get("custom_fallback"):
                recovery_action["fallback_action"] = context.get("custom_fallback")
            self.enforcement_log.append(f"Fallback recovery applied due to violations at {datetime.now().isoformat()}")
            self.last_enforcement = time.time()
            return recovery_action


# Example usage and testing
if __name__ == "__main__":
    # Create a guardrail manager
    guardrail_config = {
        "log_limit": 100,
        "default_fallback": "block_action"
    }
    guardrail_manager = GuardrailManager("TestGuardrailManager", config=guardrail_config)
    guardrail_manager.activate()

    # Create and register guardrails
    validation_gr = ValidationGuardrail("InputValidation", config={
        "default_rules": ["not_none", "string_not_empty"]
    })
    policy_gr = PolicyEnforcer("ContentPolicy", config={
        "default_policies": ["no_profanity", "content_length_limit"],
        "profanity_list": ["badword", "uglyword"],
        "max_content_length": 50
    })
    content_filter_gr = ContentFilter("ContentFilter", config={
        "blocked_words": ["forbidden", "dangerous"],
        "blocked_patterns": [r"hack[\w]*", r"exploit[\w]*"],
        "sensitive_data_regex": [r"\b\d{3}-\d{2}-\d{4}\b"],
        "block_on_violation": True
    })
    rate_limiter_gr = RateLimiter("RateLimiter", config={
        "rate_limit": 5,
        "window_size": 10.0,
        "quota_limit": 20,
        "quota_period": 60.0
    })

    guardrail_manager.register_guardrail(validation_gr)
    guardrail_manager.register_guardrail(policy_gr)
    guardrail_manager.register_guardrail(content_filter_gr)
    guardrail_manager.register_guardrail(rate_limiter_gr)

    # Test guardrail enforcement
    test_data = "This is a test with badword and SSN 123-45-6789"
    context = {
        "entity_id": "test_user_1",
        "task_type": "text_processing",
        "environment": "production",
        "user_role": "user"
    }

    # Enforce all guardrails
    success, violations = guardrail_manager.enforce_guardrails(test_data, context)
    print(f"All Guardrails Enforcement - Success: {success}")
    print(f"Violations: {json.dumps(violations, indent=2)[:500]}... (truncated)")

    # Test rate limiter separately with multiple calls
    for i in range(7):
        success, rate_violations = guardrail_manager.enforce_guardrails(f"Action {i}", context, ["RateLimiter"])
        print(f"Rate Limiter Enforcement {i+1} - Success: {success}")
        if not success:
            print(f"Rate Limit Violations: {rate_violations}")

    # Check rate limit status
    rate_status = rate_limiter_gr.get_rate_limit_status("test_user_1")
    print(f"Rate Limit Status: {rate_status}")

    # Test contextual guardrails
    success, contextual_violations = guardrail_manager.apply_contextual_guardrails(test_data, context)
    print(f"Contextual Guardrails Enforcement - Success: {success}")
    print(f"Contextual Violations: {json.dumps(contextual_violations, indent=2)[:500]}... (truncated)")

    # Apply fallback recovery if there are violations
    if violations:
        recovery = guardrail_manager.fallback_recovery(violations, context)
        print(f"Fallback Recovery: {recovery}")

    # Get monitoring data
    monitoring_data = guardrail_manager.get_monitoring_data()
    print(f"Guardrail Manager Monitoring Data: {json.dumps(monitoring_data, indent=2)[:500]}... (truncated)")
