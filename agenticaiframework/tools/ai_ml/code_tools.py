"""
Code Interpreter and Execution Tools.
"""

import logging
import sys
import io
import traceback
import shutil
import subprocess
import tempfile
import os
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
        allow_package_install: bool = True,
        install_timeout: float = 60.0,
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
        self.allow_package_install = allow_package_install
        self.install_timeout = install_timeout
        self._globals: Dict[str, Any] = {}
        self._locals: Dict[str, Any] = {}
    
    def _execute(
        self,
        code: str,
        capture_output: bool = True,
        persist_variables: bool = True,
        reset_environment: bool = False,
        packages: Optional[List[str]] = None,
        auto_install: bool = True,
        cleanup: bool = False,
        isolate_packages: bool = True,
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

        installed_packages = []
        temp_package_dir = None
        original_sys_path = None
        original_allowed = list(self.allowed_modules)
        if packages and auto_install:
            if not self.allow_package_install:
                return {
                    'code': code,
                    'status': 'error',
                    'output': None,
                    'error': 'Package installation is disabled',
                    'return_value': None,
                    'variables': {},
                }
            install_result = self._install_packages(packages, isolate=isolate_packages)
            if install_result.get('status') != 'success':
                return {
                    'code': code,
                    'status': 'error',
                    'output': None,
                    'error': install_result.get('error', 'Package installation failed'),
                    'return_value': None,
                    'variables': {},
                    'packages': install_result,
                }
            installed_packages = install_result.get('installed', [])
            temp_package_dir = install_result.get('install_dir')
            if temp_package_dir:
                original_sys_path = list(sys.path)
                sys.path.insert(0, temp_package_dir)
            # Temporarily allow installed packages
            self.allowed_modules = list(set(self.allowed_modules + [p.split('==')[0] for p in installed_packages]))
        
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
            'packages': installed_packages,
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
            if original_sys_path is not None:
                sys.path = original_sys_path
            self.allowed_modules = original_allowed
        
        if capture_output:
            stdout_val = stdout_capture.getvalue()
            stderr_val = stderr_capture.getvalue()
            
            result['output'] = stdout_val[:self.max_output_length]
            if stderr_val:
                result['stderr'] = stderr_val[:self.max_output_length]
            
            if len(stdout_val) > self.max_output_length:
                result['output_truncated'] = True
        
        if cleanup:
            self.reset()
            if temp_package_dir and os.path.isdir(temp_package_dir):
                try:
                    shutil.rmtree(temp_package_dir, ignore_errors=True)
                except Exception:
                    pass

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

    def _install_packages(self, packages: List[str], isolate: bool = True) -> Dict[str, Any]:
        """Install multiple Python packages."""
        installed = []
        errors = []
        install_dir = None

        if isolate:
            install_dir = tempfile.mkdtemp(prefix='agenticai_packages_')

        for package in packages:
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        '-m',
                        'pip',
                        'install',
                        package,
                        *(['--target', install_dir] if install_dir else []),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=self.install_timeout,
                )
                if result.returncode == 0:
                    installed.append(package)
                else:
                    errors.append({
                        'package': package,
                        'stderr': result.stderr.strip(),
                        'stdout': result.stdout.strip(),
                    })
            except subprocess.TimeoutExpired:
                errors.append({
                    'package': package,
                    'error': 'Installation timed out',
                })
            except Exception as e:  # noqa: BLE001
                errors.append({
                    'package': package,
                    'error': str(e),
                })

        if errors:
            if install_dir and os.path.isdir(install_dir):
                shutil.rmtree(install_dir, ignore_errors=True)
            return {
                'status': 'error',
                'installed': installed,
                'errors': errors,
            }

        return {
            'status': 'success',
            'installed': installed,
            'install_dir': install_dir,
        }


class JavaScriptCodeInterpreterTool(BaseTool):
    """
    Tool for executing JavaScript code safely via Node.js.
    
    Features:
    - JavaScript execution using Node.js
    - Output capture
    - Timeout enforcement
    """

    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        timeout: float = 10.0,
        max_output_length: int = 10000,
        node_path: Optional[str] = None,
        npm_path: Optional[str] = None,
        allow_package_install: bool = True,
        install_timeout: float = 120.0,
    ):
        super().__init__(config or ToolConfig(
            name="JavaScriptCodeInterpreterTool",
            description="Execute JavaScript code using Node.js"
        ))
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.node_path = node_path or shutil.which('node')
        self.npm_path = npm_path or shutil.which('npm')
        self.allow_package_install = allow_package_install
        self.install_timeout = install_timeout

    def _execute(
        self,
        code: str,
        capture_output: bool = True,
        packages: Optional[List[str]] = None,
        auto_install: bool = True,
        cleanup: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute JavaScript code via Node.js.

        Args:
            code: JavaScript code to execute
            capture_output: Capture stdout/stderr

        Returns:
            Dict with execution results
        """
        result = {
            'code': code,
            'status': 'success',
            'output': None,
            'error': None,
        }

        if not self.node_path:
            return {
                **result,
                'status': 'error',
                'error': 'Node.js not available on PATH',
            }

        work_dir = None
        try:
            use_temp_dir = bool(packages) or cleanup
            if use_temp_dir:
                work_dir = tempfile.TemporaryDirectory()

            if packages and auto_install:
                if not self.allow_package_install:
                    return {
                        **result,
                        'status': 'error',
                        'error': 'Package installation is disabled',
                    }
                if not self.npm_path:
                    return {
                        **result,
                        'status': 'error',
                        'error': 'npm not available on PATH',
                    }

                cwd = work_dir.name if work_dir else None
                init_cmd = [self.npm_path, 'init', '-y']
                subprocess.run(init_cmd, capture_output=True, text=True, timeout=self.install_timeout, cwd=cwd)

                install_cmd = [self.npm_path, 'install', *packages]
                install_result = subprocess.run(
                    install_cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.install_timeout,
                    cwd=cwd,
                )
                if install_result.returncode != 0:
                    return {
                        **result,
                        'status': 'error',
                        'error': install_result.stderr.strip() or 'npm install failed',
                        'stderr': install_result.stderr[:self.max_output_length],
                    }

            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, dir=work_dir.name if work_dir else None) as tmp:
                tmp.write(code)
                tmp_path = tmp.name

            completed = subprocess.run(
                [self.node_path, tmp_path],
                capture_output=capture_output,
                text=True,
                timeout=self.timeout,
                cwd=work_dir.name if work_dir else None,
            )

            stdout_val = completed.stdout or ""
            stderr_val = completed.stderr or ""

            result['output'] = stdout_val[:self.max_output_length]
            if stderr_val:
                result['stderr'] = stderr_val[:self.max_output_length]

            if completed.returncode != 0:
                result['status'] = 'error'
                result['error'] = stderr_val.strip() or f"Process exited with code {completed.returncode}"

            if len(stdout_val) > self.max_output_length:
                result['output_truncated'] = True

        except subprocess.TimeoutExpired:
            result['status'] = 'error'
            result['error'] = 'Execution timed out'
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        finally:
            try:
                if 'tmp_path' in locals():
                    import os
                    os.unlink(tmp_path)
            except Exception:
                pass
            if work_dir is not None:
                work_dir.cleanup()

        return result


__all__ = ['CodeInterpreterTool', 'JavaScriptCodeInterpreterTool']
