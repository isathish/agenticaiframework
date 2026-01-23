"""
Enterprise Sandbox Module.

Provides isolated execution environments, code sandboxing,
and safe execution contexts for agent operations.

Example:
    # Execute code in sandbox
    sandbox = Sandbox()
    
    result = await sandbox.execute(
        code="result = 2 + 2",
        timeout=5.0,
    )
    print(result.output)  # {'result': 4}
    
    # With restricted globals
    safe_sandbox = RestrictedSandbox()
    result = await safe_sandbox.execute(user_code)
"""

from __future__ import annotations

import asyncio
import sys
import io
import traceback
import copy
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)
from datetime import datetime
from functools import wraps
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from enum import Enum
import logging
import ast
import builtins

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SandboxError(Exception):
    """Sandbox execution error."""
    pass


class SecurityViolationError(SandboxError):
    """Security policy violation."""
    pass


class TimeoutViolationError(SandboxError):
    """Execution timeout exceeded."""
    pass


class MemoryViolationError(SandboxError):
    """Memory limit exceeded."""
    pass


class ExecutionStatus(str, Enum):
    """Execution status."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class ExecutionResult:
    """Result of sandbox execution."""
    status: ExecutionStatus
    output: Dict[str, Any] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    error: Optional[str] = None
    error_type: Optional[str] = None
    traceback: Optional[str] = None
    
    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ExecutionStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "output": self.output,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
            "error_type": self.error_type,
        }


@dataclass
class SecurityPolicy:
    """Security policy for sandbox."""
    allowed_imports: Set[str] = field(default_factory=lambda: {
        "math", "random", "datetime", "json", "re", "collections",
        "itertools", "functools", "operator", "string", "typing",
    })
    blocked_imports: Set[str] = field(default_factory=lambda: {
        "os", "sys", "subprocess", "shutil", "socket", "requests",
        "urllib", "ftplib", "smtplib", "pickle", "marshal", "importlib",
    })
    allowed_builtins: Set[str] = field(default_factory=lambda: {
        "abs", "all", "any", "bool", "chr", "dict", "divmod", "enumerate",
        "filter", "float", "format", "frozenset", "getattr", "hasattr",
        "hash", "hex", "int", "isinstance", "issubclass", "iter", "len",
        "list", "map", "max", "min", "next", "oct", "ord", "pow", "print",
        "range", "repr", "reversed", "round", "set", "slice", "sorted",
        "str", "sum", "tuple", "type", "zip",
    })
    blocked_attributes: Set[str] = field(default_factory=lambda: {
        "__import__", "__builtins__", "__code__", "__globals__",
        "__subclasses__", "__bases__", "__mro__", "__class__",
        "__reduce__", "__reduce_ex__", "exec", "eval", "compile",
    })
    max_iterations: int = 1000000
    max_recursion: int = 100
    max_memory_mb: float = 100.0
    max_output_size: int = 10000
    
    def is_import_allowed(self, module: str) -> bool:
        """Check if an import is allowed."""
        base_module = module.split('.')[0]
        
        if base_module in self.blocked_imports:
            return False
        
        if self.allowed_imports:
            return base_module in self.allowed_imports
        
        return True
    
    def is_builtin_allowed(self, name: str) -> bool:
        """Check if a builtin is allowed."""
        return name in self.allowed_builtins
    
    def is_attribute_allowed(self, name: str) -> bool:
        """Check if an attribute access is allowed."""
        return name not in self.blocked_attributes


class CodeAnalyzer:
    """
    Static code analyzer for security checks.
    """
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
    
    def analyze(self, code: str) -> List[str]:
        """
        Analyze code for security violations.
        
        Returns list of violation messages.
        """
        violations = []
        
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return [f"Syntax error: {e}"]
        
        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not self.policy.is_import_allowed(alias.name):
                        violations.append(f"Blocked import: {alias.name}")
            
            elif isinstance(node, ast.ImportFrom):
                if node.module and not self.policy.is_import_allowed(node.module):
                    violations.append(f"Blocked import: {node.module}")
            
            # Check function calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.policy.blocked_attributes:
                        violations.append(f"Blocked function: {node.func.id}")
            
            # Check attribute access
            elif isinstance(node, ast.Attribute):
                if node.attr in self.policy.blocked_attributes:
                    violations.append(f"Blocked attribute: {node.attr}")
            
            # Check for eval/exec
            if isinstance(node, ast.Name):
                if node.id in ("eval", "exec", "compile"):
                    violations.append(f"Blocked function: {node.id}")
        
        return violations


class SafeImporter:
    """
    Safe import handler for sandbox.
    """
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
        self._imported: Dict[str, Any] = {}
    
    def safe_import(self, name: str, *args, **kwargs) -> Any:
        """Safely import a module."""
        if not self.policy.is_import_allowed(name):
            raise SecurityViolationError(f"Import of '{name}' is not allowed")
        
        if name in self._imported:
            return self._imported[name]
        
        module = __builtins__['__import__'](name, *args, **kwargs)
        self._imported[name] = module
        return module


class Sandbox(ABC):
    """Abstract sandbox for code execution."""
    
    @abstractmethod
    async def execute(
        self,
        code: str,
        timeout: float = 10.0,
        globals_dict: Optional[Dict[str, Any]] = None,
        locals_dict: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """Execute code in sandbox."""
        pass


class LocalSandbox(Sandbox):
    """
    Local Python sandbox with security restrictions.
    """
    
    def __init__(
        self,
        policy: Optional[SecurityPolicy] = None,
        enable_static_analysis: bool = True,
    ):
        """
        Initialize sandbox.
        
        Args:
            policy: Security policy
            enable_static_analysis: Enable static code analysis
        """
        self.policy = policy or SecurityPolicy()
        self._analyzer = CodeAnalyzer(self.policy) if enable_static_analysis else None
        self._importer = SafeImporter(self.policy)
    
    def _create_safe_builtins(self) -> Dict[str, Any]:
        """Create restricted builtins."""
        safe_builtins = {}
        
        for name in dir(builtins):
            if self.policy.is_builtin_allowed(name):
                safe_builtins[name] = getattr(builtins, name)
        
        # Add safe import
        safe_builtins['__import__'] = self._importer.safe_import
        
        return safe_builtins
    
    def _create_globals(
        self,
        user_globals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create restricted globals."""
        globals_dict = {
            '__builtins__': self._create_safe_builtins(),
            '__name__': '__sandbox__',
            '__doc__': None,
        }
        
        if user_globals:
            # Filter dangerous items from user globals
            for key, value in user_globals.items():
                if not key.startswith('_'):
                    globals_dict[key] = value
        
        return globals_dict
    
    async def execute(
        self,
        code: str,
        timeout: float = 10.0,
        globals_dict: Optional[Dict[str, Any]] = None,
        locals_dict: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute code in sandbox.
        
        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            globals_dict: Optional global variables
            locals_dict: Optional local variables
            
        Returns:
            Execution result
        """
        # Static analysis
        if self._analyzer:
            violations = self._analyzer.analyze(code)
            if violations:
                return ExecutionResult(
                    status=ExecutionStatus.SECURITY_VIOLATION,
                    error="; ".join(violations),
                    error_type="SecurityViolationError",
                )
        
        # Prepare execution environment
        safe_globals = self._create_globals(globals_dict)
        exec_locals = dict(locals_dict) if locals_dict else {}
        
        # Capture output
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        start_time = time.time()
        
        try:
            # Execute with timeout
            loop = asyncio.get_event_loop()
            
            def run_code():
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(compile(code, '<sandbox>', 'exec'), safe_globals, exec_locals)
            
            await asyncio.wait_for(
                loop.run_in_executor(None, run_code),
                timeout=timeout,
            )
            
            duration = (time.time() - start_time) * 1000
            
            # Extract output variables
            output = {
                k: v for k, v in exec_locals.items()
                if not k.startswith('_')
            }
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                output=output,
                stdout=stdout_capture.getvalue()[:self.policy.max_output_size],
                stderr=stderr_capture.getvalue()[:self.policy.max_output_size],
                duration_ms=duration,
            )
            
        except asyncio.TimeoutError:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                stdout=stdout_capture.getvalue()[:self.policy.max_output_size],
                stderr=stderr_capture.getvalue()[:self.policy.max_output_size],
                duration_ms=duration,
                error=f"Execution timed out after {timeout}s",
                error_type="TimeoutError",
            )
            
        except SecurityViolationError as e:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                status=ExecutionStatus.SECURITY_VIOLATION,
                stdout=stdout_capture.getvalue()[:self.policy.max_output_size],
                stderr=stderr_capture.getvalue()[:self.policy.max_output_size],
                duration_ms=duration,
                error=str(e),
                error_type="SecurityViolationError",
            )
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                stdout=stdout_capture.getvalue()[:self.policy.max_output_size],
                stderr=stderr_capture.getvalue()[:self.policy.max_output_size],
                duration_ms=duration,
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
            )


class RestrictedSandbox(LocalSandbox):
    """
    Highly restricted sandbox for untrusted code.
    """
    
    def __init__(self):
        super().__init__(
            policy=SecurityPolicy(
                allowed_imports={"math", "random", "json", "datetime"},
                allowed_builtins={
                    "abs", "all", "any", "bool", "dict", "float", "int",
                    "len", "list", "max", "min", "print", "range", "round",
                    "set", "sorted", "str", "sum", "tuple", "zip",
                },
                max_iterations=10000,
                max_recursion=50,
            ),
            enable_static_analysis=True,
        )


class FunctionSandbox:
    """
    Sandbox for executing user-provided functions.
    """
    
    def __init__(
        self,
        policy: Optional[SecurityPolicy] = None,
    ):
        self._sandbox = LocalSandbox(policy)
    
    async def execute_function(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> ExecutionResult:
        """
        Execute a function in sandbox.
        
        Args:
            func: Function to execute
            args: Function arguments
            kwargs: Function keyword arguments
            timeout: Execution timeout
            
        Returns:
            Execution result
        """
        kwargs = kwargs or {}
        
        # Create code to call the function
        code = """
__result__ = __func__(*__args__, **__kwargs__)
"""
        
        result = await self._sandbox.execute(
            code,
            timeout=timeout,
            globals_dict={
                '__func__': func,
                '__args__': args,
                '__kwargs__': kwargs,
            },
        )
        
        if result.success:
            result.output = {'result': result.output.get('__result__')}
        
        return result


class IsolatedContext:
    """
    Isolated execution context with state management.
    """
    
    def __init__(
        self,
        sandbox: Optional[Sandbox] = None,
        initial_state: Optional[Dict[str, Any]] = None,
    ):
        self._sandbox = sandbox or LocalSandbox()
        self._state: Dict[str, Any] = dict(initial_state) if initial_state else {}
        self._history: List[Dict[str, Any]] = []
    
    async def execute(
        self,
        code: str,
        timeout: float = 10.0,
    ) -> ExecutionResult:
        """Execute code with persistent state."""
        result = await self._sandbox.execute(
            code,
            timeout=timeout,
            globals_dict=self._state,
        )
        
        if result.success:
            # Update state with new values
            self._state.update(result.output)
            
            # Record history
            self._history.append({
                "code": code,
                "output": result.output,
                "timestamp": time.time(),
            })
        
        return result
    
    @property
    def state(self) -> Dict[str, Any]:
        """Get current state."""
        return dict(self._state)
    
    @property
    def history(self) -> List[Dict[str, Any]]:
        """Get execution history."""
        return list(self._history)
    
    def reset(self) -> None:
        """Reset state and history."""
        self._state.clear()
        self._history.clear()
    
    def set_state(self, key: str, value: Any) -> None:
        """Set a state value."""
        self._state[key] = value
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        return self._state.get(key, default)


def sandbox_function(
    timeout: float = 10.0,
    policy: Optional[SecurityPolicy] = None,
) -> Callable:
    """
    Decorator to execute a function in sandbox.
    
    Example:
        @sandbox_function(timeout=5.0)
        def compute(x):
            return x * 2
    """
    def decorator(func: Callable) -> Callable:
        sandbox = FunctionSandbox(policy)
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> ExecutionResult:
            return await sandbox.execute_function(func, args, kwargs, timeout)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> ExecutionResult:
            return asyncio.run(sandbox.execute_function(func, args, kwargs, timeout))
        
        wrapper = async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        wrapper.__sandbox__ = sandbox
        return wrapper
    
    return decorator


__all__ = [
    # Exceptions
    "SandboxError",
    "SecurityViolationError",
    "TimeoutViolationError",
    "MemoryViolationError",
    # Enums
    "ExecutionStatus",
    # Data classes
    "ExecutionResult",
    "SecurityPolicy",
    # Analyzers
    "CodeAnalyzer",
    "SafeImporter",
    # Sandboxes
    "Sandbox",
    "LocalSandbox",
    "RestrictedSandbox",
    "FunctionSandbox",
    "IsolatedContext",
    # Decorators
    "sandbox_function",
]
