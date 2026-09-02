"""Minimal GraphQL query-language parser and executor — stdlib-only.

Implements the executable subset of the GraphQL spec (October 2021):

* documents with multiple operations (query / mutation / subscription),
  anonymous or named, with variable definitions (types + defaults)
* selection sets, aliases, arguments, nested selections
* fragment definitions, fragment spreads and inline fragments
* ``@include(if:)`` / ``@skip(if:)`` directives
* all value literals (int, float, string incl. block strings, boolean,
  null, enum, list, input object) and variables

Execution walks the AST against a *resolver lookup* callback, so it is
independent of any particular schema representation.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------


@dataclass
class Variable:
    name: str


@dataclass
class Argument:
    name: str
    value: Any  # literal (python value) | Variable | Enum(str) | list | dict


@dataclass
class Directive:
    name: str
    arguments: List[Argument] = field(default_factory=list)


@dataclass
class Field:
    name: str
    alias: Optional[str] = None
    arguments: List[Argument] = field(default_factory=list)
    directives: List[Directive] = field(default_factory=list)
    selection_set: List["Selection"] = field(default_factory=list)

    @property
    def response_key(self) -> str:
        return self.alias or self.name


@dataclass
class FragmentSpread:
    name: str
    directives: List[Directive] = field(default_factory=list)


@dataclass
class InlineFragment:
    type_condition: Optional[str]
    directives: List[Directive] = field(default_factory=list)
    selection_set: List["Selection"] = field(default_factory=list)


Selection = Union[Field, FragmentSpread, InlineFragment]


@dataclass
class VariableDefinition:
    name: str
    type: str
    default: Any = None
    has_default: bool = False


@dataclass
class OperationDefinition:
    operation: str  # query | mutation | subscription
    name: Optional[str]
    variables: List[VariableDefinition]
    directives: List[Directive]
    selection_set: List[Selection]


@dataclass
class FragmentDefinition:
    name: str
    type_condition: str
    directives: List[Directive]
    selection_set: List[Selection]


@dataclass
class Document:
    operations: List[OperationDefinition]
    fragments: Dict[str, FragmentDefinition]


class EnumValue(str):
    """Marker type for enum literals so they can be told apart from strings."""


class GraphQLSyntaxError(Exception):
    def __init__(self, message: str, line: int = 0, column: int = 0):
        super().__init__(f"{message} (line {line}, column {column})" if line else message)
        self.line, self.column = line, column


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    (?P<ws>[\s,\ufeff]+) |
    (?P<comment>\#[^\r\n]*) |
    (?P<block_string>\"\"\"(?:\\\"\"\"|(?!\"\"\").)*\"\"\") |
    (?P<string>\"(?:[^\"\\\r\n]|\\.)*\") |
    (?P<number>-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?) |
    (?P<name>[_A-Za-z][_0-9A-Za-z]*) |
    (?P<spread>\.\.\.) |
    (?P<punct>[!$&()\[\]{}:=@|])
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass
class _Token:
    kind: str
    value: str
    pos: int


def _tokenize(source: str) -> List[_Token]:
    tokens: List[_Token] = []
    pos = 0
    while pos < len(source):
        m = _TOKEN_RE.match(source, pos)
        if not m:
            line = source.count("\n", 0, pos) + 1
            col = pos - source.rfind("\n", 0, pos)
            raise GraphQLSyntaxError(f"Unexpected character {source[pos]!r}", line, col)
        kind = m.lastgroup or ""
        if kind not in ("ws", "comment"):
            tokens.append(_Token(kind, m.group(0), pos))
        pos = m.end()
    tokens.append(_Token("eof", "", pos))
    return tokens


def _unescape_string(raw: str) -> str:
    body = raw[1:-1]

    def repl(m: re.Match) -> str:
        esc = m.group(1)
        if esc[0] == "u":
            return chr(int(esc[1:], 16))
        return {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", '"': '"', "\\": "\\", "/": "/"}[esc]

    return re.sub(r"\\(u[0-9A-Fa-f]{4}|.)", repl, body)


def _dedent_block_string(raw: str) -> str:
    body = raw[3:-3].replace('\\"""', '"""')
    lines = body.split("\n")
    common: Optional[int] = None
    for line in lines[1:]:
        stripped = line.lstrip(" \t")
        if not stripped:
            continue
        indent = len(line) - len(stripped)
        common = indent if common is None else min(common, indent)
    if common:
        lines = [lines[0]] + [ln[common:] for ln in lines[1:]]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.tokens = _tokenize(source)
        self.i = 0

    # -- helpers ------------------------------------------------------------

    def peek(self, offset: int = 0) -> _Token:
        return self.tokens[min(self.i + offset, len(self.tokens) - 1)]

    def next(self) -> _Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def error(self, message: str, tok: Optional[_Token] = None) -> GraphQLSyntaxError:
        tok = tok or self.peek()
        line = self.source.count("\n", 0, tok.pos) + 1
        col = tok.pos - self.source.rfind("\n", 0, tok.pos)
        return GraphQLSyntaxError(message, line, col)

    def expect_punct(self, value: str) -> None:
        tok = self.next()
        if tok.value != value:
            raise self.error(f"Expected {value!r}, got {tok.value!r}", tok)

    def maybe_punct(self, value: str) -> bool:
        if self.peek().value == value and self.peek().kind in ("punct", "spread"):
            self.i += 1
            return True
        return False

    def expect_name(self, value: Optional[str] = None) -> str:
        tok = self.next()
        if tok.kind != "name" or (value is not None and tok.value != value):
            raise self.error(f"Expected name{' ' + repr(value) if value else ''}, got {tok.value!r}", tok)
        return tok.value

    # -- grammar ------------------------------------------------------------

    def parse_document(self) -> Document:
        operations: List[OperationDefinition] = []
        fragments: Dict[str, FragmentDefinition] = {}
        while self.peek().kind != "eof":
            tok = self.peek()
            if tok.value == "{":
                operations.append(OperationDefinition("query", None, [], [], self.parse_selection_set()))
            elif tok.kind == "name" and tok.value in ("query", "mutation", "subscription"):
                operations.append(self.parse_operation())
            elif tok.kind == "name" and tok.value == "fragment":
                frag = self.parse_fragment()
                fragments[frag.name] = frag
            else:
                raise self.error(f"Unexpected token {tok.value!r}", tok)
        if not operations:
            raise GraphQLSyntaxError("Document contains no operations")
        return Document(operations, fragments)

    def parse_operation(self) -> OperationDefinition:
        op = self.expect_name()
        name = self.expect_name() if self.peek().kind == "name" else None
        variables: List[VariableDefinition] = []
        if self.maybe_punct("("):
            while not self.maybe_punct(")"):
                self.expect_punct("$")
                var_name = self.expect_name()
                self.expect_punct(":")
                var_type = self.parse_type()
                default, has_default = None, False
                if self.maybe_punct("="):
                    default, has_default = self.parse_value(const=True), True
                variables.append(VariableDefinition(var_name, var_type, default, has_default))
        directives = self.parse_directives()
        return OperationDefinition(op, name, variables, directives, self.parse_selection_set())

    def parse_fragment(self) -> FragmentDefinition:
        self.expect_name("fragment")
        name = self.expect_name()
        if name == "on":
            raise self.error("Fragment name cannot be 'on'")
        self.expect_name("on")
        type_cond = self.expect_name()
        directives = self.parse_directives()
        return FragmentDefinition(name, type_cond, directives, self.parse_selection_set())

    def parse_type(self) -> str:
        if self.maybe_punct("["):
            inner = self.parse_type()
            self.expect_punct("]")
            t = f"[{inner}]"
        else:
            t = self.expect_name()
        if self.maybe_punct("!"):
            t += "!"
        return t

    def parse_selection_set(self) -> List[Selection]:
        self.expect_punct("{")
        selections: List[Selection] = []
        while not self.maybe_punct("}"):
            if self.peek().kind == "eof":
                raise self.error("Unterminated selection set")
            selections.append(self.parse_selection())
        return selections

    def parse_selection(self) -> Selection:
        if self.maybe_punct("..."):
            if self.peek().kind == "name" and self.peek().value != "on":
                return FragmentSpread(self.expect_name(), self.parse_directives())
            type_cond = None
            if self.peek().value == "on":
                self.expect_name("on")
                type_cond = self.expect_name()
            directives = self.parse_directives()
            return InlineFragment(type_cond, directives, self.parse_selection_set())
        name = self.expect_name()
        alias = None
        if self.maybe_punct(":"):
            alias, name = name, self.expect_name()
        arguments = self.parse_arguments()
        directives = self.parse_directives()
        selection_set = self.parse_selection_set() if self.peek().value == "{" else []
        return Field(name, alias, arguments, directives, selection_set)

    def parse_arguments(self) -> List[Argument]:
        args: List[Argument] = []
        if self.maybe_punct("("):
            while not self.maybe_punct(")"):
                name = self.expect_name()
                self.expect_punct(":")
                args.append(Argument(name, self.parse_value()))
        return args

    def parse_directives(self) -> List[Directive]:
        directives: List[Directive] = []
        while self.maybe_punct("@"):
            directives.append(Directive(self.expect_name(), self.parse_arguments()))
        return directives

    def parse_value(self, const: bool = False) -> Any:
        tok = self.next()
        if tok.value == "$" and tok.kind == "punct":
            if const:
                raise self.error("Variables are not allowed in this position", tok)
            return Variable(self.expect_name())
        if tok.value == "[":
            items = []
            while not self.maybe_punct("]"):
                items.append(self.parse_value(const))
            return items
        if tok.value == "{":
            obj: Dict[str, Any] = {}
            while not self.maybe_punct("}"):
                key = self.expect_name()
                self.expect_punct(":")
                obj[key] = self.parse_value(const)
            return obj
        if tok.kind == "number":
            return float(tok.value) if any(c in tok.value for c in ".eE") else int(tok.value)
        if tok.kind == "string":
            return _unescape_string(tok.value)
        if tok.kind == "block_string":
            return _dedent_block_string(tok.value)
        if tok.kind == "name":
            if tok.value == "true":
                return True
            if tok.value == "false":
                return False
            if tok.value == "null":
                return None
            return EnumValue(tok.value)
        raise self.error(f"Unexpected token {tok.value!r} in value", tok)


def parse(source: str) -> Document:
    parser = _Parser(source)
    return parser.parse_document()


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class GraphQLExecutionError(Exception):
    def __init__(self, message: str, path: Optional[List[Union[str, int]]] = None):
        super().__init__(message)
        self.path = path or []


@dataclass
class FieldContext:
    """Passed to resolvers as ``info``."""
    field_name: str
    parent_type: str
    return_type: Optional[str]
    path: List[Union[str, int]]
    context: Dict[str, Any]
    variables: Dict[str, Any]
    operation_name: Optional[str]
    selection_set: List[Selection] = field(default_factory=list)


ResolverLookup = Callable[[str, str], Optional[Callable[..., Any]]]
FieldTypeLookup = Callable[[str, str], Optional[str]]


def unwrap_type(type_name: Optional[str]) -> Optional[str]:
    """``[User!]!`` -> ``User``."""
    if not type_name:
        return None
    return type_name.strip("[]!").strip("[]!")


class Executor:
    """Execute a parsed document.

    ``resolver_lookup(parent_type, field_name)`` returns a callable
    ``resolver(parent, info, **args)`` (sync or async) or ``None`` to fall back
    to attribute / mapping access on the parent value.

    ``field_type_lookup(parent_type, field_name)`` returns the declared
    GraphQL type of the field (e.g. ``"[User!]!"``) so nested resolvers can
    be located; it may return ``None``.

    ``middlewares`` is a list of ``async (next_fn, parent, info, **kwargs)``
    callables applied around every resolver, first-added = outermost.
    """

    def __init__(
        self,
        resolver_lookup: ResolverLookup,
        field_type_lookup: Optional[FieldTypeLookup] = None,
        type_of_value: Optional[Callable[[Any, Optional[str]], Optional[str]]] = None,
        middlewares: Optional[List[Callable[..., Awaitable[Any]]]] = None,
        root_types: Optional[Dict[str, str]] = None,
        max_depth: int = 32,
    ) -> None:
        self._resolver_lookup = resolver_lookup
        self._field_type_lookup = field_type_lookup or (lambda *_: None)
        self._type_of_value = type_of_value or (lambda _v, declared: declared)
        self._middlewares = middlewares or []
        self._root_types = root_types or {"query": "Query", "mutation": "Mutation", "subscription": "Subscription"}
        self._max_depth = max_depth

    async def execute(
        self,
        document: Union[str, Document],
        *,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        root_value: Any = None,
    ) -> Tuple[Optional[Dict[str, Any]], List[GraphQLExecutionError]]:
        doc = parse(document) if isinstance(document, str) else document
        operation = self._select_operation(doc, operation_name)
        coerced = self._coerce_variables(operation, variables or {})
        errors: List[GraphQLExecutionError] = []
        root_type = self._root_types[operation.operation]
        state = _ExecState(doc, coerced, context or {}, operation.name, errors)
        # Mutations execute serially, queries may run concurrently.
        data = await self._execute_selection_set(
            state, operation.selection_set, root_type, root_value, [], serial=operation.operation == "mutation",
        )
        return data, errors

    # -- setup ----------------------------------------------------------------

    @staticmethod
    def _select_operation(doc: Document, name: Optional[str]) -> OperationDefinition:
        if name is None:
            if len(doc.operations) > 1:
                raise GraphQLExecutionError("Must provide operation name if query contains multiple operations")
            return doc.operations[0]
        for op in doc.operations:
            if op.name == name:
                return op
        raise GraphQLExecutionError(f"Unknown operation named {name!r}")

    @staticmethod
    def _coerce_variables(op: OperationDefinition, supplied: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for var in op.variables:
            if var.name in supplied:
                out[var.name] = supplied[var.name]
            elif var.has_default:
                out[var.name] = _literal_to_python(var.default, {})
            elif var.type.endswith("!"):
                raise GraphQLExecutionError(f"Variable ${var.name} of required type {var.type} was not provided")
            else:
                out[var.name] = None
        return out

    # -- execution ------------------------------------------------------------

    async def _execute_selection_set(
        self, state: "_ExecState", selections: List[Selection], parent_type: str,
        parent: Any, path: List[Union[str, int]], *, serial: bool = False,
    ) -> Dict[str, Any]:
        if len(path) > self._max_depth:
            raise GraphQLExecutionError("Query depth limit exceeded", path)
        grouped = self._collect_fields(state, selections, parent_type, parent)
        result: Dict[str, Any] = {}
        if serial:
            for key, fields in grouped.items():
                result[key] = await self._execute_field(state, fields, parent_type, parent, path + [key])
        else:
            import asyncio
            values = await asyncio.gather(*(
                self._execute_field(state, fields, parent_type, parent, path + [key])
                for key, fields in grouped.items()
            ))
            result = dict(zip(grouped.keys(), values))
        return result

    def _collect_fields(
        self, state: "_ExecState", selections: List[Selection], parent_type: str, parent: Any,
        visited: Optional[set] = None,
    ) -> Dict[str, List[Field]]:
        grouped: Dict[str, List[Field]] = {}
        visited = visited if visited is not None else set()
        for sel in selections:
            if not self._should_include(sel.directives, state.variables):
                continue
            if isinstance(sel, Field):
                grouped.setdefault(sel.response_key, []).append(sel)
            elif isinstance(sel, FragmentSpread):
                if sel.name in visited:
                    continue
                frag = state.document.fragments.get(sel.name)
                if frag is None:
                    raise GraphQLExecutionError(f"Unknown fragment {sel.name!r}")
                if not self._type_matches(frag.type_condition, parent_type, parent):
                    continue
                for k, v in self._collect_fields(state, frag.selection_set, parent_type, parent, visited | {sel.name}).items():
                    grouped.setdefault(k, []).extend(v)
            elif isinstance(sel, InlineFragment):
                if sel.type_condition and not self._type_matches(sel.type_condition, parent_type, parent):
                    continue
                for k, v in self._collect_fields(state, sel.selection_set, parent_type, parent, visited).items():
                    grouped.setdefault(k, []).extend(v)
        return grouped

    def _type_matches(self, condition: str, parent_type: str, parent: Any) -> bool:
        if condition == parent_type:
            return True
        actual = self._type_of_value(parent, parent_type)
        if actual == condition:
            return True
        typename = getattr(parent, "__typename__", None) or (parent.get("__typename") if isinstance(parent, dict) else None)
        return typename == condition or type(parent).__name__ == condition

    @staticmethod
    def _should_include(directives: List[Directive], variables: Dict[str, Any]) -> bool:
        for d in directives:
            if d.name in ("include", "skip"):
                cond = next((a.value for a in d.arguments if a.name == "if"), None)
                value = bool(_literal_to_python(cond, variables))
                if (d.name == "include" and not value) or (d.name == "skip" and value):
                    return False
        return True

    async def _execute_field(
        self, state: "_ExecState", fields: List[Field], parent_type: str, parent: Any,
        path: List[Union[str, int]],
    ) -> Any:
        first = fields[0]
        if first.name == "__typename":
            return self._type_of_value(parent, parent_type) or parent_type
        args = {a.name: _literal_to_python(a.value, state.variables) for a in first.arguments}
        declared = self._field_type_lookup(parent_type, first.name)
        info = FieldContext(
            field_name=first.name, parent_type=parent_type, return_type=declared, path=path,
            context=state.context, variables=state.variables, operation_name=state.operation_name,
            selection_set=[s for f in fields for s in f.selection_set],
        )
        try:
            value = await self._resolve(parent_type, first.name, parent, info, args)
            return await self._complete_value(state, fields, declared, value, path)
        except GraphQLExecutionError as exc:
            if not exc.path:
                exc.path = path
            state.errors.append(exc)
            return None
        except Exception as exc:  # noqa: BLE001 - resolver errors become GraphQL errors
            state.errors.append(GraphQLExecutionError(str(exc), path))
            return None

    async def _resolve(self, parent_type: str, field_name: str, parent: Any, info: FieldContext, args: Dict[str, Any]) -> Any:
        resolver = self._resolver_lookup(parent_type, field_name)
        if resolver is None:
            return _default_resolve(parent, field_name, args)

        async def base(parent_, info_, **kwargs):
            out = resolver(parent_, info_, **kwargs)
            return await out if inspect.isawaitable(out) else out

        chain = base
        for mw in reversed(self._middlewares):
            chain = _wrap_middleware(mw, chain)
        return await chain(parent, info, **args)

    async def _complete_value(
        self, state: "_ExecState", fields: List[Field], declared: Optional[str], value: Any,
        path: List[Union[str, int]],
    ) -> Any:
        if inspect.isawaitable(value):
            value = await value
        if value is None:
            if declared and declared.endswith("!"):
                raise GraphQLExecutionError(f"Cannot return null for non-nullable field {'.'.join(map(str, path))}", path)
            return None
        inner_declared = declared[:-1] if declared and declared.endswith("!") else declared
        sub_selections = [s for f in fields for s in f.selection_set]
        if isinstance(value, (list, tuple, set)) or (inspect.isgenerator(value)):
            item_type = inner_declared[1:-1] if inner_declared and inner_declared.startswith("[") else inner_declared
            import asyncio
            return list(await asyncio.gather(*(
                self._complete_value(state, fields, item_type, item, path + [idx])
                for idx, item in enumerate(value)
            )))
        if not sub_selections:
            return _serialize_leaf(value)
        child_type = self._type_of_value(value, unwrap_type(inner_declared)) or unwrap_type(inner_declared) or type(value).__name__
        return await self._execute_selection_set(state, sub_selections, child_type, value, path)


@dataclass
class _ExecState:
    document: Document
    variables: Dict[str, Any]
    context: Dict[str, Any]
    operation_name: Optional[str]
    errors: List[GraphQLExecutionError]


def _wrap_middleware(mw: Callable[..., Awaitable[Any]], nxt: Callable[..., Awaitable[Any]]):
    async def wrapped(parent, info, **kwargs):
        return await mw(nxt, parent, info, **kwargs)
    return wrapped


def _literal_to_python(value: Any, variables: Dict[str, Any]) -> Any:
    if isinstance(value, Variable):
        return variables.get(value.name)
    if isinstance(value, EnumValue):
        return str(value)
    if isinstance(value, list):
        return [_literal_to_python(v, variables) for v in value]
    if isinstance(value, dict):
        return {k: _literal_to_python(v, variables) for k, v in value.items()}
    return value


def _default_resolve(parent: Any, name: str, args: Dict[str, Any]) -> Any:
    if parent is None:
        return None
    if isinstance(parent, dict):
        value = parent.get(name)
    else:
        value = getattr(parent, name, None)
    if callable(value) and not isinstance(value, type):
        try:
            value = value(**args) if args else value()
        except TypeError:
            value = value()
    return value


def _serialize_leaf(value: Any) -> Any:
    from datetime import date, datetime
    from decimal import Decimal
    from enum import Enum
    from uuid import UUID

    if isinstance(value, Enum):
        return value.name
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {k: _serialize_leaf(v) for k, v in value.items()}
    if hasattr(value, "__dict__"):
        return {k: _serialize_leaf(v) for k, v in vars(value).items() if not k.startswith("_")}
    return str(value)


__all__ = [
    "parse", "Document", "OperationDefinition", "FragmentDefinition", "Field", "FragmentSpread",
    "InlineFragment", "Argument", "Directive", "Variable", "VariableDefinition", "EnumValue",
    "GraphQLSyntaxError", "GraphQLExecutionError", "Executor", "FieldContext", "unwrap_type",
]
