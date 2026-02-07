"""
Enterprise CLI Module.

Provides command-line interface patterns, argument parsing,
interactive prompts, and CLI application scaffolding.

Example:
    # Create CLI app
    app = CLI("myapp", version="1.0.0")
    
    # Add commands with decorators
    @app.command()
    def greet(name: str, loud: bool = False):
        '''Greet someone.'''
        msg = f"Hello, {name}!"
        print(msg.upper() if loud else msg)
    
    @app.command()
    @argument("count", type=int, help="Number of times")
    @option("--prefix", "-p", default="", help="Message prefix")
    def repeat(message: str, count: int, prefix: str):
        '''Repeat a message.'''
        for _ in range(count):
            print(f"{prefix}{message}")
    
    # Run CLI
    app.run()
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CLIError(Exception):
    """CLI error."""
    pass


class CommandError(CLIError):
    """Command execution error."""
    pass


class ArgumentError(CLIError):
    """Argument parsing error."""
    pass


class Color(str, Enum):
    """Terminal colors."""
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


class Style(str, Enum):
    """Text styles."""
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    HIDDEN = "\033[8m"
    RESET = "\033[0m"


@dataclass
class ArgumentSpec:
    """Argument specification."""
    name: str
    type: Type = str
    default: Any = None
    required: bool = True
    help: str = ""
    choices: Optional[List[Any]] = None
    nargs: Optional[str] = None


@dataclass
class OptionSpec:
    """Option specification."""
    name: str
    short: Optional[str] = None
    type: Type = str
    default: Any = None
    required: bool = False
    help: str = ""
    is_flag: bool = False
    choices: Optional[List[Any]] = None
    envvar: Optional[str] = None


@dataclass
class CommandSpec:
    """Command specification."""
    name: str
    handler: Callable
    help: str = ""
    arguments: List[ArgumentSpec] = field(default_factory=list)
    options: List[OptionSpec] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    hidden: bool = False


class Output:
    """Output formatting utilities."""
    
    def __init__(self, no_color: bool = False):
        self._no_color = no_color or not sys.stdout.isatty()
    
    def _colorize(self, text: str, color: Color) -> str:
        """Apply color to text."""
        if self._no_color:
            return text
        return f"{color.value}{text}{Color.RESET.value}"
    
    def _stylize(self, text: str, style: Style) -> str:
        """Apply style to text."""
        if self._no_color:
            return text
        return f"{style.value}{text}{Style.RESET.value}"
    
    def echo(self, message: str = "", **kwargs: Any) -> None:
        """Print a message."""
        print(message, **kwargs)
    
    def info(self, message: str) -> None:
        """Print info message."""
        self.echo(self._colorize(f"[INFO] {message}", Color.BLUE))
    
    def success(self, message: str) -> None:
        """Print success message."""
        self.echo(self._colorize(f"[OK] {message}", Color.GREEN))
    
    def warning(self, message: str) -> None:
        """Print warning message."""
        self.echo(self._colorize(f"[WARN] {message}", Color.YELLOW))
    
    def error(self, message: str) -> None:
        """Print error message."""
        self.echo(self._colorize(f"[ERROR] {message}", Color.RED))
    
    def debug(self, message: str) -> None:
        """Print debug message."""
        self.echo(self._colorize(f"[DEBUG] {message}", Color.DIM))
    
    def bold(self, text: str) -> str:
        """Make text bold."""
        return self._stylize(text, Style.BOLD)
    
    def dim(self, text: str) -> str:
        """Make text dim."""
        return self._stylize(text, Style.DIM)
    
    def table(
        self,
        headers: List[str],
        rows: List[List[Any]],
        padding: int = 2,
    ) -> None:
        """Print a table."""
        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))
        
        # Print header
        header_row = " " * padding
        header_row += (" " * padding).join(
            str(h).ljust(widths[i]) for i, h in enumerate(headers)
        )
        self.echo(self.bold(header_row))
        
        # Print separator
        sep = " " * padding
        sep += (" " * padding).join("-" * w for w in widths)
        self.echo(sep)
        
        # Print rows
        for row in rows:
            row_str = " " * padding
            row_str += (" " * padding).join(
                str(cell).ljust(widths[i]) for i, cell in enumerate(row)
            )
            self.echo(row_str)
    
    def progress(
        self,
        current: int,
        total: int,
        width: int = 40,
        prefix: str = "",
    ) -> None:
        """Print progress bar."""
        percent = current / total if total > 0 else 0
        filled = int(width * percent)
        bar = "█" * filled + "░" * (width - filled)
        
        self.echo(f"\r{prefix}[{bar}] {percent:.1%}", end="")
        
        if current >= total:
            self.echo()


class Prompt:
    """Interactive prompt utilities."""
    
    def __init__(self, output: Optional[Output] = None):
        self._output = output or Output()
    
    def ask(
        self,
        question: str,
        default: Optional[str] = None,
    ) -> str:
        """Ask for text input."""
        default_str = f" [{default}]" if default else ""
        answer = input(f"{question}{default_str}: ").strip()
        return answer or default or ""
    
    def confirm(
        self,
        question: str,
        default: bool = False,
    ) -> bool:
        """Ask for yes/no confirmation."""
        default_str = "[Y/n]" if default else "[y/N]"
        answer = input(f"{question} {default_str}: ").strip().lower()
        
        if not answer:
            return default
        
        return answer in ("y", "yes", "true", "1")
    
    def choose(
        self,
        question: str,
        choices: List[str],
        default: Optional[int] = None,
    ) -> str:
        """Choose from a list of options."""
        self._output.echo(question)
        
        for i, choice in enumerate(choices):
            marker = ">" if i == default else " "
            self._output.echo(f"  {marker} [{i + 1}] {choice}")
        
        while True:
            default_str = f" [{default + 1}]" if default is not None else ""
            answer = input(f"Enter choice{default_str}: ").strip()
            
            if not answer and default is not None:
                return choices[default]
            
            try:
                idx = int(answer) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
            except ValueError:
                pass
            
            self._output.error("Invalid choice. Please try again.")
    
    def password(self, prompt: str = "Password") -> str:
        """Ask for password (hidden input)."""
        import getpass
        return getpass.getpass(f"{prompt}: ")


class Command(ABC):
    """Abstract command."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get command name."""
        pass
    
    @property
    @abstractmethod
    def help(self) -> str:
        """Get command help."""
        pass
    
    @abstractmethod
    def execute(self, **kwargs: Any) -> int:
        """Execute the command."""
        pass


class CLI:
    """
    Command-line interface application.
    """
    
    def __init__(
        self,
        name: str = "cli",
        version: str = "1.0.0",
        description: str = "",
    ):
        self._name = name
        self._version = version
        self._description = description
        self._commands: Dict[str, CommandSpec] = {}
        self._groups: Dict[str, List[str]] = {}
        self._output = Output()
        self._prompt = Prompt(self._output)
        self._middleware: List[Callable] = []
        
        # Add built-in commands
        self._add_builtin_commands()
    
    def _add_builtin_commands(self) -> None:
        """Add built-in commands."""
        @self.command(name="version", help="Show version information")
        def version_cmd() -> None:
            self._output.echo(f"{self._name} v{self._version}")
    
    @property
    def output(self) -> Output:
        """Get output helper."""
        return self._output
    
    @property
    def prompt(self) -> Prompt:
        """Get prompt helper."""
        return self._prompt
    
    def command(
        self,
        name: Optional[str] = None,
        help: str = "",
        aliases: Optional[List[str]] = None,
        hidden: bool = False,
    ) -> Callable:
        """
        Decorator to register a command.
        
        Example:
            @app.command()
            def greet(name: str):
                '''Greet someone.'''
                print(f"Hello, {name}!")
        """
        def decorator(func: Callable) -> Callable:
            cmd_name = name or func.__name__.replace("_", "-")
            cmd_help = help or func.__doc__ or ""
            
            # Extract arguments and options from function signature
            arguments, options = self._extract_params(func)
            
            spec = CommandSpec(
                name=cmd_name,
                handler=func,
                help=cmd_help.strip(),
                arguments=arguments,
                options=options,
                aliases=aliases or [],
                hidden=hidden,
            )
            
            self._commands[cmd_name] = spec
            
            # Register aliases
            for alias in spec.aliases:
                self._commands[alias] = spec
            
            return func
        
        return decorator
    
    def _extract_params(
        self,
        func: Callable,
    ) -> Tuple[List[ArgumentSpec], List[OptionSpec]]:
        """Extract arguments and options from function signature."""
        arguments = []
        options = []
        
        sig = inspect.signature(func)
        
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "ctx"):
                continue
            
            # Check for custom annotations
            arg_spec = getattr(param, '_argument', None)
            opt_spec = getattr(param, '_option', None)
            
            if arg_spec:
                arguments.append(arg_spec)
            elif opt_spec:
                options.append(opt_spec)
            elif param.default == inspect.Parameter.empty:
                # Required positional argument
                arguments.append(ArgumentSpec(
                    name=param_name,
                    type=param.annotation if param.annotation != inspect.Parameter.empty else str,
                    required=True,
                ))
            else:
                # Optional argument (option)
                is_flag = param.annotation == bool or isinstance(param.default, bool)
                options.append(OptionSpec(
                    name=param_name,
                    type=param.annotation if param.annotation != inspect.Parameter.empty else type(param.default),
                    default=param.default,
                    is_flag=is_flag,
                ))
        
        return arguments, options
    
    def group(self, name: str) -> 'CommandGroup':
        """Create a command group."""
        self._groups[name] = []
        return CommandGroup(self, name)
    
    def use(self, middleware: Callable) -> None:
        """Add middleware."""
        self._middleware.append(middleware)
    
    def run(self, args: Optional[List[str]] = None) -> int:
        """Run the CLI."""
        args = args or sys.argv[1:]
        
        if not args:
            self._show_help()
            return 0
        
        cmd_name = args[0]
        
        if cmd_name in ("-h", "--help", "help"):
            if len(args) > 1:
                return self._show_command_help(args[1])
            self._show_help()
            return 0
        
        if cmd_name in ("-v", "--version"):
            self._output.echo(f"{self._name} v{self._version}")
            return 0
        
        # Find command
        spec = self._commands.get(cmd_name)
        
        if not spec:
            self._output.error(f"Unknown command: {cmd_name}")
            self._show_help()
            return 1
        
        # Parse arguments
        try:
            parsed = self._parse_args(spec, args[1:])
            
            # Apply middleware
            for mw in self._middleware:
                parsed = mw(spec, parsed)
                if parsed is None:
                    return 1
            
            # Execute command
            result = self._execute_command(spec, parsed)
            
            if asyncio.iscoroutine(result):
                result = asyncio.run(result)
            
            return result if isinstance(result, int) else 0
            
        except ArgumentError as e:
            self._output.error(str(e))
            return 1
        except CommandError as e:
            self._output.error(str(e))
            return 1
        except KeyboardInterrupt:
            self._output.echo("\nAborted.")
            return 130
        except Exception as e:
            self._output.error(f"Error: {e}")
            logger.exception("Command execution failed")
            return 1
    
    def _parse_args(
        self,
        spec: CommandSpec,
        args: List[str],
    ) -> Dict[str, Any]:
        """Parse command arguments."""
        parser = argparse.ArgumentParser(
            prog=f"{self._name} {spec.name}",
            description=spec.help,
        )
        
        # Add arguments
        for arg in spec.arguments:
            parser.add_argument(
                arg.name,
                type=arg.type,
                help=arg.help,
                choices=arg.choices,
                nargs=arg.nargs,
            )
        
        # Add options
        for opt in spec.options:
            names = [f"--{opt.name.replace('_', '-')}"]
            if opt.short:
                names.insert(0, f"-{opt.short}")
            
            if opt.is_flag:
                parser.add_argument(
                    *names,
                    action="store_true",
                    default=opt.default,
                    help=opt.help,
                )
            else:
                parser.add_argument(
                    *names,
                    type=opt.type,
                    default=opt.default,
                    required=opt.required,
                    help=opt.help,
                    choices=opt.choices,
                )
        
        parsed = parser.parse_args(args)
        return vars(parsed)
    
    def _execute_command(
        self,
        spec: CommandSpec,
        kwargs: Dict[str, Any],
    ) -> Any:
        """Execute a command."""
        return spec.handler(**kwargs)
    
    def _show_help(self) -> None:
        """Show help message."""
        self._output.echo(f"\n{self._output.bold(self._name)} v{self._version}")
        
        if self._description:
            self._output.echo(f"\n{self._description}")
        
        self._output.echo(f"\n{self._output.bold('Usage:')}")
        self._output.echo(f"  {self._name} <command> [options] [arguments]")
        
        self._output.echo(f"\n{self._output.bold('Commands:')}")
        
        # Group commands
        for name, spec in sorted(self._commands.items()):
            if spec.hidden or name != spec.name:  # Skip aliases
                continue
            
            aliases_str = ""
            if spec.aliases:
                aliases_str = f" ({', '.join(spec.aliases)})"
            
            self._output.echo(f"  {name:<20}{spec.help}{aliases_str}")
        
        self._output.echo(f"\n{self._output.bold('Options:')}")
        self._output.echo("  -h, --help         Show help")
        self._output.echo("  -v, --version      Show version")
        self._output.echo()
    
    def _show_command_help(self, cmd_name: str) -> int:
        """Show help for a specific command."""
        spec = self._commands.get(cmd_name)
        
        if not spec:
            self._output.error(f"Unknown command: {cmd_name}")
            return 1
        
        self._output.echo(f"\n{self._output.bold(spec.name)} - {spec.help}")
        
        self._output.echo(f"\n{self._output.bold('Usage:')}")
        
        usage = f"  {self._name} {spec.name}"
        for arg in spec.arguments:
            usage += f" <{arg.name}>"
        for opt in spec.options:
            opt_name = f"--{opt.name.replace('_', '-')}"
            if opt.required:
                usage += f" {opt_name}=<value>"
            else:
                usage += f" [{opt_name}]"
        
        self._output.echo(usage)
        
        if spec.arguments:
            self._output.echo(f"\n{self._output.bold('Arguments:')}")
            for arg in spec.arguments:
                self._output.echo(f"  {arg.name:<20}{arg.help}")
        
        if spec.options:
            self._output.echo(f"\n{self._output.bold('Options:')}")
            for opt in spec.options:
                opt_name = f"--{opt.name.replace('_', '-')}"
                if opt.short:
                    opt_name = f"-{opt.short}, {opt_name}"
                
                default_str = f" (default: {opt.default})" if opt.default else ""
                self._output.echo(f"  {opt_name:<20}{opt.help}{default_str}")
        
        self._output.echo()
        return 0


class CommandGroup:
    """Command group for organizing related commands."""
    
    def __init__(self, cli: CLI, name: str):
        self._cli = cli
        self._name = name
    
    def command(
        self,
        name: Optional[str] = None,
        help: str = "",
        **kwargs: Any,
    ) -> Callable:
        """Add command to group."""
        def decorator(func: Callable) -> Callable:
            cmd_name = f"{self._name}:{name or func.__name__}"
            return self._cli.command(name=cmd_name, help=help, **kwargs)(func)
        return decorator


# Decorators
def argument(
    name: str,
    type: Type = str,
    help: str = "",
    choices: Optional[List[Any]] = None,
    nargs: Optional[str] = None,
) -> Callable:
    """
    Decorator to add an argument to a command.
    """
    def decorator(func: Callable) -> Callable:
        if not hasattr(func, '_arguments'):
            func._arguments = []
        
        func._arguments.append(ArgumentSpec(
            name=name,
            type=type,
            help=help,
            choices=choices,
            nargs=nargs,
        ))
        
        return func
    
    return decorator


def option(
    name: str,
    short: Optional[str] = None,
    type: Type = str,
    default: Any = None,
    help: str = "",
    required: bool = False,
    is_flag: bool = False,
    envvar: Optional[str] = None,
) -> Callable:
    """
    Decorator to add an option to a command.
    """
    def decorator(func: Callable) -> Callable:
        if not hasattr(func, '_options'):
            func._options = []
        
        # Check environment variable
        actual_default = default
        if envvar:
            env_value = os.environ.get(envvar)
            if env_value is not None:
                actual_default = type(env_value) if type != bool else env_value.lower() in ('true', '1', 'yes')
        
        func._options.append(OptionSpec(
            name=name.lstrip('-'),
            short=short.lstrip('-') if short else None,
            type=type,
            default=actual_default,
            help=help,
            required=required,
            is_flag=is_flag,
            envvar=envvar,
        ))
        
        return func
    
    return decorator


def pass_context(func: Callable) -> Callable:
    """
    Decorator to pass CLI context to command.
    """
    func._pass_context = True
    return func


# Factory functions
def create_cli(
    name: str = "cli",
    version: str = "1.0.0",
    description: str = "",
) -> CLI:
    """Create a CLI application."""
    return CLI(name, version, description)


def create_output(no_color: bool = False) -> Output:
    """Create output helper."""
    return Output(no_color)


def create_prompt(output: Optional[Output] = None) -> Prompt:
    """Create prompt helper."""
    return Prompt(output)


__all__ = [
    # Exceptions
    "CLIError",
    "CommandError",
    "ArgumentError",
    # Enums
    "Color",
    "Style",
    # Data classes
    "ArgumentSpec",
    "OptionSpec",
    "CommandSpec",
    # Core classes
    "Output",
    "Prompt",
    "Command",
    "CLI",
    "CommandGroup",
    # Decorators
    "argument",
    "option",
    "pass_context",
    # Factory
    "create_cli",
    "create_output",
    "create_prompt",
]
