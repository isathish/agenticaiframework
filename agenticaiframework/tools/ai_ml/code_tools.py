"""
Code Interpreter and Execution Tools.
"""

import logging
import sys
import io
import traceback
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class CodeInterpreterTool(BaseTool):
    """
    Tool for executing Python code safely.
    
    Features:
    - Python code execution
    - Sandboxed environment
    - Output capture
    - Variable persistence
    - Package installation
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        allowed_modules: Optional[List[str]] = None,
        timeout: float = 30.0,
        max_output_length: int = 10000,
    ):
        super().__init__(config or ToolConfig(
            name="CodeInterpreterTool",
            description="Execute Python code safely"
        ))
        self.allowed_modules = allowed_modules or [
            'math', 'json', 're', 'datetime', 'collections',
            'itertools', 'functools', 'random', 'statistics',
            'numpy', 'pandas', 'matplotlib',
        ]
        self.timeout = timeout
        self.max_output_length = max_output_length
        self._globals: Dict[str, Any] = {}
        self._locals: Dict[str, Any] = {}
    
    def _execute(
        self,
        code: str,
        capture_output: bool = True,
        persist_variables: bool = True,
        reset_environment: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute Python code.
        
        Args:
            code: Python code to execute
            capture_output: Capture stdout/stderr
            persist_variables: Keep variables between calls
            reset_environment: Reset execution environment
            
        Returns:
            Dict with execution results
        """
        if reset_environment:
            self._globals = {}
            self._locals = {}
        
        # Set up safe globals
        safe_globals = {
            '__builtins__': self._get_safe_builtins(),
            **self._globals,
        }
        
        # Capture output
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        if capture_output:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
        
        result = {
            'code': code,
            'status': 'success',
            'output': None,
            'error': None,
            'return_value': None,
            'variables': {},
        }
        
        try:
            # Compile and execute
            compiled = compile(code, '<code>', 'exec')
            
            # Execute with timeout (simplified - real timeout needs threading)
            exec_locals = dict(self._locals) if persist_variables else {}
            exec(compiled, safe_globals, exec_locals)
            
            # Get last expression value if any
            try:
                last_expr = compile(code.split('\n')[-1], '<expr>', 'eval')
                result['return_value'] = eval(last_expr, safe_globals, exec_locals)
            except:
                pass
            
            # Update persistent state
            if persist_variables:
                self._locals.update(exec_locals)
                self._globals.update(
                    {k: v for k, v in safe_globals.items() if k != '__builtins__'}
                )
            
            # Get variable info
            result['variables'] = {
                k: type(v).__name__
                for k, v in exec_locals.items()
                if not k.startswith('_')
            }
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = {
                'type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc(),
            }
        
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        if capture_output:
            stdout_val = stdout_capture.getvalue()
            stderr_val = stderr_capture.getvalue()
            
            result['output'] = stdout_val[:self.max_output_length]
            if stderr_val:
                result['stderr'] = stderr_val[:self.max_output_length]
            
            if len(stdout_val) > self.max_output_length:
                result['output_truncated'] = True
        
        return result
    
    def _get_safe_builtins(self) -> Dict[str, Any]:
        """Get safe subset of builtins."""
        safe = {}
        
        # Safe types
        safe_names = [
            'True', 'False', 'None',
            'abs', 'all', 'any', 'bin', 'bool', 'bytearray', 'bytes',
            'callable', 'chr', 'complex', 'dict', 'divmod', 'enumerate',
            'filter', 'float', 'format', 'frozenset', 'hash', 'hex',
            'int', 'isinstance', 'issubclass', 'iter', 'len', 'list',
            'map', 'max', 'min', 'next', 'object', 'oct', 'ord', 'pow',
            'print', 'range', 'repr', 'reversed', 'round', 'set',
            'slice', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
        ]
        
        import builtins
        for name in safe_names:
            if hasattr(builtins, name):
                safe[name] = getattr(builtins, name)
        
        # Safe import
        safe['__import__'] = self._safe_import
        
        return safe
    
    def _safe_import(
        self,
        name: str,
        globals: Dict = None,
        locals: Dict = None,
        fromlist: List = None,
        level: int = 0,
    ):
        """Safe import function."""
        # Check if module is allowed
        base_module = name.split('.')[0]
        
        if base_module not in self.allowed_modules:
            raise ImportError(
                f"Module '{name}' is not allowed. "
                f"Allowed modules: {self.allowed_modules}"
            )
        
        return __import__(name, globals, locals, fromlist or [], level)
    
    def get_variables(self) -> Dict[str, Any]:
        """Get current variable values."""
        return {
            k: repr(v)[:100]
            for k, v in self._locals.items()
            if not k.startswith('_')
        }
    
    def set_variable(self, name: str, value: Any):
        """Set a variable in the execution environment."""
        self._locals[name] = value
    
    def reset(self):
        """Reset the execution environment."""
        self._globals = {}
        self._locals = {}
    
    def install_package(self, package: str) -> Dict[str, Any]:
        """Install a Python package (use with caution)."""
        import subprocess
        
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', package],
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            return {
                'status': 'success' if result.returncode == 0 else 'error',
                'package': package,
                'stdout': result.stdout,
                'stderr': result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                'status': 'error',
                'error': 'Installation timed out',
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
            }


__all__ = ['CodeInterpreterTool']
