"""
Enterprise Merge Module.

Provides data merging, conflict resolution, and deep merge
capabilities for complex data structures.

Example:
    # Create merger
    merger = create_merger()
    
    # Simple merge
    result = merger.merge(
        {"name": "John", "age": 30},
        {"age": 31, "city": "NYC"}
    )
    # {"name": "John", "age": 31, "city": "NYC"}
    
    # With conflict resolution
    @on_conflict("last_wins")
    def custom_merge(base: dict, update: dict) -> dict:
        return merge(base, update)
    
    # Deep merge with strategies
    result = deep_merge(
        nested_dict1,
        nested_dict2,
        strategy=MergeStrategy.UNION,
    )
"""

from __future__ import annotations

import copy
import logging
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
    Set,
    Tuple,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')


class MergeError(Exception):
    """Merge error."""
    pass


class ConflictError(MergeError):
    """Conflict resolution error."""
    pass


class MergeStrategy(str, Enum):
    """Merge strategies."""
    OVERRIDE = "override"  # Later value wins
    PRESERVE = "preserve"  # Earlier value wins
    UNION = "union"  # Combine collections
    INTERSECTION = "intersection"  # Keep common
    DEEP = "deep"  # Recursive merge
    CUSTOM = "custom"  # Custom handler


class ConflictResolution(str, Enum):
    """Conflict resolution strategies."""
    FIRST_WINS = "first_wins"
    LAST_WINS = "last_wins"
    ERROR = "error"
    MERGE = "merge"
    MAX = "max"
    MIN = "min"
    SUM = "sum"


@dataclass
class ConflictInfo:
    """Information about a conflict."""
    path: str
    key: str
    value1: Any
    value2: Any
    resolved_value: Optional[Any] = None
    resolution: Optional[ConflictResolution] = None


@dataclass
class MergeResult(Generic[T]):
    """Result of a merge operation."""
    data: T
    conflicts: List[ConflictInfo] = field(default_factory=list)
    merged_count: int = 0
    skipped_count: int = 0


@dataclass
class MergeConfig:
    """Merge configuration."""
    strategy: MergeStrategy = MergeStrategy.DEEP
    conflict_resolution: ConflictResolution = ConflictResolution.LAST_WINS
    deep_merge_lists: bool = False
    preserve_none: bool = False
    max_depth: int = 100


class ConflictResolver(ABC):
    """Abstract conflict resolver."""
    
    @abstractmethod
    def resolve(
        self,
        key: str,
        value1: Any,
        value2: Any,
        path: str = "",
    ) -> Any:
        """Resolve a conflict between two values."""
        pass


class DefaultConflictResolver(ConflictResolver):
    """Default conflict resolver."""
    
    def __init__(
        self,
        resolution: ConflictResolution = ConflictResolution.LAST_WINS,
    ):
        self._resolution = resolution
    
    def resolve(
        self,
        key: str,
        value1: Any,
        value2: Any,
        path: str = "",
    ) -> Any:
        """Resolve conflict."""
        if self._resolution == ConflictResolution.FIRST_WINS:
            return value1
        
        elif self._resolution == ConflictResolution.LAST_WINS:
            return value2
        
        elif self._resolution == ConflictResolution.ERROR:
            raise ConflictError(
                f"Conflict at {path}.{key}: {value1} vs {value2}"
            )
        
        elif self._resolution == ConflictResolution.MERGE:
            if isinstance(value1, dict) and isinstance(value2, dict):
                return {**value1, **value2}
            elif isinstance(value1, list) and isinstance(value2, list):
                return value1 + value2
            elif isinstance(value1, set) and isinstance(value2, set):
                return value1 | value2
            return value2
        
        elif self._resolution == ConflictResolution.MAX:
            try:
                return max(value1, value2)
            except TypeError:
                return value2
        
        elif self._resolution == ConflictResolution.MIN:
            try:
                return min(value1, value2)
            except TypeError:
                return value2
        
        elif self._resolution == ConflictResolution.SUM:
            try:
                return value1 + value2
            except TypeError:
                return value2
        
        return value2


class CallbackConflictResolver(ConflictResolver):
    """Conflict resolver using callback function."""
    
    def __init__(
        self,
        callback: Callable[[str, Any, Any], Any],
    ):
        self._callback = callback
    
    def resolve(
        self,
        key: str,
        value1: Any,
        value2: Any,
        path: str = "",
    ) -> Any:
        """Resolve using callback."""
        return self._callback(key, value1, value2)


class Merger:
    """
    Main merger class for combining data structures.
    """
    
    def __init__(
        self,
        config: Optional[MergeConfig] = None,
        resolver: Optional[ConflictResolver] = None,
    ):
        self._config = config or MergeConfig()
        self._resolver = resolver or DefaultConflictResolver(
            self._config.conflict_resolution
        )
    
    def merge(
        self,
        *sources: Dict[str, Any],
        track_conflicts: bool = False,
    ) -> Union[Dict[str, Any], MergeResult[Dict[str, Any]]]:
        """
        Merge multiple dictionaries.
        """
        if not sources:
            return {} if not track_conflicts else MergeResult(data={})
        
        result = copy.deepcopy(sources[0])
        conflicts = []
        merged_count = 0
        
        for source in sources[1:]:
            result, new_conflicts, count = self._merge_dict(
                result,
                source,
                track_conflicts=track_conflicts,
            )
            conflicts.extend(new_conflicts)
            merged_count += count
        
        if track_conflicts:
            return MergeResult(
                data=result,
                conflicts=conflicts,
                merged_count=merged_count,
            )
        
        return result
    
    def _merge_dict(
        self,
        base: Dict[str, Any],
        update: Dict[str, Any],
        path: str = "",
        depth: int = 0,
        track_conflicts: bool = False,
    ) -> Tuple[Dict[str, Any], List[ConflictInfo], int]:
        """Merge two dictionaries."""
        conflicts = []
        merged_count = 0
        
        if depth > self._config.max_depth:
            raise MergeError(f"Max merge depth exceeded at {path}")
        
        result = dict(base)
        
        for key, value in update.items():
            current_path = f"{path}.{key}" if path else key
            
            if key not in result:
                # New key
                result[key] = copy.deepcopy(value)
                merged_count += 1
            
            elif result[key] is None and not self._config.preserve_none:
                # Replace None
                result[key] = copy.deepcopy(value)
                merged_count += 1
            
            elif (
                self._config.strategy == MergeStrategy.DEEP
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Deep merge dictionaries
                result[key], sub_conflicts, sub_count = self._merge_dict(
                    result[key],
                    value,
                    current_path,
                    depth + 1,
                    track_conflicts,
                )
                conflicts.extend(sub_conflicts)
                merged_count += sub_count
            
            elif (
                self._config.deep_merge_lists
                and isinstance(result[key], list)
                and isinstance(value, list)
            ):
                # Merge lists
                result[key] = self._merge_lists(result[key], value)
                merged_count += 1
            
            else:
                # Conflict
                if result[key] != value:
                    resolved = self._resolver.resolve(
                        key,
                        result[key],
                        value,
                        path,
                    )
                    
                    if track_conflicts:
                        conflicts.append(ConflictInfo(
                            path=path,
                            key=key,
                            value1=result[key],
                            value2=value,
                            resolved_value=resolved,
                            resolution=self._config.conflict_resolution,
                        ))
                    
                    result[key] = resolved
                    merged_count += 1
        
        return result, conflicts, merged_count
    
    def _merge_lists(
        self,
        list1: List[Any],
        list2: List[Any],
    ) -> List[Any]:
        """Merge two lists."""
        if self._config.strategy == MergeStrategy.UNION:
            # Unique values
            seen = set()
            result = []
            
            for item in list1 + list2:
                key = self._get_hashable(item)
                if key not in seen:
                    seen.add(key)
                    result.append(item)
            
            return result
        
        elif self._config.strategy == MergeStrategy.INTERSECTION:
            set1 = {self._get_hashable(item) for item in list1}
            return [item for item in list2 if self._get_hashable(item) in set1]
        
        else:
            # Default: concatenate
            return list1 + list2
    
    def _get_hashable(self, item: Any) -> Any:
        """Get hashable representation of item."""
        if isinstance(item, dict):
            return tuple(sorted(item.items()))
        elif isinstance(item, list):
            return tuple(item)
        return item


class DeepMerger:
    """
    Advanced deep merger with path-based control.
    """
    
    def __init__(
        self,
        default_strategy: MergeStrategy = MergeStrategy.DEEP,
        path_strategies: Optional[Dict[str, MergeStrategy]] = None,
    ):
        self._default_strategy = default_strategy
        self._path_strategies = path_strategies or {}
    
    def merge(
        self,
        base: Any,
        update: Any,
        path: str = "",
    ) -> Any:
        """Deep merge with path-based strategy."""
        strategy = self._path_strategies.get(path, self._default_strategy)
        
        if base is None:
            return copy.deepcopy(update)
        
        if update is None:
            return copy.deepcopy(base)
        
        # Dict merge
        if isinstance(base, dict) and isinstance(update, dict):
            result = {}
            
            all_keys = set(base.keys()) | set(update.keys())
            
            for key in all_keys:
                child_path = f"{path}.{key}" if path else key
                
                if key in base and key in update:
                    result[key] = self.merge(
                        base[key],
                        update[key],
                        child_path,
                    )
                elif key in base:
                    result[key] = copy.deepcopy(base[key])
                else:
                    result[key] = copy.deepcopy(update[key])
            
            return result
        
        # List merge
        if isinstance(base, list) and isinstance(update, list):
            if strategy == MergeStrategy.UNION:
                return self._union_lists(base, update)
            elif strategy == MergeStrategy.PRESERVE:
                return copy.deepcopy(base)
            else:
                return copy.deepcopy(update)
        
        # Set merge
        if isinstance(base, set) and isinstance(update, set):
            if strategy == MergeStrategy.UNION:
                return base | update
            elif strategy == MergeStrategy.INTERSECTION:
                return base & update
            elif strategy == MergeStrategy.PRESERVE:
                return copy.deepcopy(base)
            else:
                return copy.deepcopy(update)
        
        # Scalar values
        if strategy == MergeStrategy.PRESERVE:
            return copy.deepcopy(base)
        
        return copy.deepcopy(update)
    
    def _union_lists(
        self,
        list1: List[Any],
        list2: List[Any],
    ) -> List[Any]:
        """Union of two lists preserving order."""
        result = list(list1)
        
        for item in list2:
            if item not in result:
                result.append(item)
        
        return result


class ObjectMerger(Generic[T]):
    """
    Merge objects of the same type.
    """
    
    def __init__(
        self,
        cls: type,
        resolver: Optional[ConflictResolver] = None,
    ):
        self._cls = cls
        self._resolver = resolver or DefaultConflictResolver()
    
    def merge(
        self,
        obj1: T,
        obj2: T,
    ) -> T:
        """Merge two objects."""
        if hasattr(obj1, '__dict__') and hasattr(obj2, '__dict__'):
            merged_dict = {}
            
            all_keys = set(obj1.__dict__.keys()) | set(obj2.__dict__.keys())
            
            for key in all_keys:
                val1 = getattr(obj1, key, None)
                val2 = getattr(obj2, key, None)
                
                if val1 is None:
                    merged_dict[key] = val2
                elif val2 is None:
                    merged_dict[key] = val1
                elif val1 == val2:
                    merged_dict[key] = val1
                else:
                    merged_dict[key] = self._resolver.resolve(key, val1, val2)
            
            # Create new instance
            result = object.__new__(self._cls)
            result.__dict__.update(merged_dict)
            return result
        
        raise MergeError(f"Cannot merge objects of type {type(obj1)}")


class DiffMerger:
    """
    Merge based on computed diffs.
    """
    
    def __init__(self):
        self._changes: List[Dict[str, Any]] = []
    
    def diff(
        self,
        base: Dict[str, Any],
        target: Dict[str, Any],
        path: str = "",
    ) -> List[Dict[str, Any]]:
        """Compute diff between two dicts."""
        changes = []
        
        all_keys = set(base.keys()) | set(target.keys())
        
        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            
            if key not in base:
                changes.append({
                    "type": "add",
                    "path": current_path,
                    "value": target[key],
                })
            elif key not in target:
                changes.append({
                    "type": "remove",
                    "path": current_path,
                    "old_value": base[key],
                })
            elif isinstance(base[key], dict) and isinstance(target[key], dict):
                changes.extend(self.diff(base[key], target[key], current_path))
            elif base[key] != target[key]:
                changes.append({
                    "type": "change",
                    "path": current_path,
                    "old_value": base[key],
                    "new_value": target[key],
                })
        
        return changes
    
    def apply(
        self,
        base: Dict[str, Any],
        changes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Apply diff changes to base."""
        result = copy.deepcopy(base)
        
        for change in changes:
            path = change["path"]
            parts = path.split(".")
            
            # Navigate to parent
            current = result
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            key = parts[-1]
            
            if change["type"] == "add":
                current[key] = change["value"]
            elif change["type"] == "remove":
                current.pop(key, None)
            elif change["type"] == "change":
                current[key] = change["new_value"]
        
        return result
    
    def merge_three_way(
        self,
        ancestor: Dict[str, Any],
        ours: Dict[str, Any],
        theirs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[ConflictInfo]]:
        """
        Three-way merge (like git).
        """
        our_changes = self.diff(ancestor, ours)
        their_changes = self.diff(ancestor, theirs)
        
        conflicts = []
        merged_changes = []
        
        # Index changes by path
        our_by_path = {c["path"]: c for c in our_changes}
        their_by_path = {c["path"]: c for c in their_changes}
        
        all_paths = set(our_by_path.keys()) | set(their_by_path.keys())
        
        for path in all_paths:
            our_change = our_by_path.get(path)
            their_change = their_by_path.get(path)
            
            if our_change and not their_change:
                merged_changes.append(our_change)
            elif their_change and not our_change:
                merged_changes.append(their_change)
            elif our_change and their_change:
                if our_change == their_change:
                    merged_changes.append(our_change)
                else:
                    # Conflict
                    conflicts.append(ConflictInfo(
                        path=path,
                        key=path.split(".")[-1],
                        value1=our_change.get("new_value") or our_change.get("value"),
                        value2=their_change.get("new_value") or their_change.get("value"),
                    ))
                    # Default: theirs wins
                    merged_changes.append(their_change)
        
        result = self.apply(ancestor, merged_changes)
        return result, conflicts


# Utility functions
def deep_merge(
    *dicts: Dict[str, Any],
    strategy: MergeStrategy = MergeStrategy.DEEP,
    conflict_resolution: ConflictResolution = ConflictResolution.LAST_WINS,
) -> Dict[str, Any]:
    """
    Deep merge multiple dictionaries.
    """
    config = MergeConfig(strategy=strategy, conflict_resolution=conflict_resolution)
    merger = Merger(config)
    return merger.merge(*dicts)


def shallow_merge(
    *dicts: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Shallow merge (update only top level).
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


def merge_with(
    key_fn: Callable[[Any], Any],
    *lists: List[Any],
) -> List[Any]:
    """
    Merge lists using a key function.
    """
    seen = {}
    
    for lst in lists:
        for item in lst:
            key = key_fn(item)
            seen[key] = item  # Last wins
    
    return list(seen.values())


# Decorators
def on_conflict(
    resolution: Union[str, ConflictResolution],
) -> Callable:
    """
    Decorator to set conflict resolution for merge function.
    
    Example:
        @on_conflict("last_wins")
        def merge_configs(base, update):
            return deep_merge(base, update)
    """
    if isinstance(resolution, str):
        resolution = ConflictResolution(resolution)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            kwargs['conflict_resolution'] = resolution
            return func(*args, **kwargs)
        return wrapper
    
    return decorator


def merge_handler(
    strategy: MergeStrategy = MergeStrategy.DEEP,
) -> Callable:
    """
    Decorator to create a merge handler.
    
    Example:
        @merge_handler(strategy=MergeStrategy.UNION)
        def merge_lists(a, b):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            kwargs['_merge_strategy'] = strategy
            return func(*args, **kwargs)
        return wrapper
    
    return decorator


# Factory functions
def create_merger(
    strategy: MergeStrategy = MergeStrategy.DEEP,
    conflict_resolution: ConflictResolution = ConflictResolution.LAST_WINS,
    **kwargs: Any,
) -> Merger:
    """Create a merger."""
    config = MergeConfig(
        strategy=strategy,
        conflict_resolution=conflict_resolution,
        **kwargs,
    )
    return Merger(config)


def create_deep_merger(
    path_strategies: Optional[Dict[str, MergeStrategy]] = None,
) -> DeepMerger:
    """Create a deep merger with path strategies."""
    return DeepMerger(path_strategies=path_strategies)


def create_diff_merger() -> DiffMerger:
    """Create a diff-based merger."""
    return DiffMerger()


def create_conflict_resolver(
    resolution: ConflictResolution = ConflictResolution.LAST_WINS,
) -> ConflictResolver:
    """Create a conflict resolver."""
    return DefaultConflictResolver(resolution)


def create_callback_resolver(
    callback: Callable[[str, Any, Any], Any],
) -> ConflictResolver:
    """Create a callback-based conflict resolver."""
    return CallbackConflictResolver(callback)


__all__ = [
    # Exceptions
    "MergeError",
    "ConflictError",
    # Enums
    "MergeStrategy",
    "ConflictResolution",
    # Data classes
    "ConflictInfo",
    "MergeResult",
    "MergeConfig",
    # Core classes
    "ConflictResolver",
    "DefaultConflictResolver",
    "CallbackConflictResolver",
    "Merger",
    "DeepMerger",
    "ObjectMerger",
    "DiffMerger",
    # Utility functions
    "deep_merge",
    "shallow_merge",
    "merge_with",
    # Decorators
    "on_conflict",
    "merge_handler",
    # Factory functions
    "create_merger",
    "create_deep_merger",
    "create_diff_merger",
    "create_conflict_resolver",
    "create_callback_resolver",
]
