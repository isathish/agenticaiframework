"""
Enterprise Dependency Manager Module.

Dependency tracking, version management, vulnerability
scanning, and dependency graph analysis.

Example:
    # Create dependency manager
    deps = create_dependency_manager()
    
    # Add dependency
    await deps.add(
        name="requests",
        version="2.31.0",
        dep_type=DependencyType.RUNTIME,
    )
    
    # Check vulnerabilities
    vulns = await deps.check_vulnerabilities("requests")
    
    # Get dependency graph
    graph = await deps.get_dependency_graph()
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Dependency error."""
    pass


class CircularDependencyError(DependencyError):
    """Circular dependency error."""
    pass


class VersionConflictError(DependencyError):
    """Version conflict error."""
    pass


class DependencyType(str, Enum):
    """Dependency type."""
    RUNTIME = "runtime"
    DEVELOPMENT = "development"
    BUILD = "build"
    TEST = "test"
    OPTIONAL = "optional"
    PEER = "peer"


class VulnerabilitySeverity(str, Enum):
    """Vulnerability severity."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UpdateType(str, Enum):
    """Update type."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


@dataclass
class Version:
    """Semantic version."""
    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease: str = ""
    build: str = ""
    
    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version
    
    def __lt__(self, other: Version) -> bool:
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        return self.patch < other.patch
    
    @classmethod
    def parse(cls, version_str: str) -> Version:
        """Parse version string."""
        pattern = r"^v?(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.]+))?(?:\+([a-zA-Z0-9.]+))?$"
        match = re.match(pattern, version_str.strip())
        
        if not match:
            return Version()
        
        return Version(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=match.group(4) or "",
            build=match.group(5) or "",
        )


@dataclass
class Dependency:
    """Dependency."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    version: str = ""
    dep_type: DependencyType = DependencyType.RUNTIME
    
    # Relationships
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    
    # Constraints
    version_constraint: str = ""
    optional: bool = False
    
    # Metadata
    description: str = ""
    license: str = ""
    repository: str = ""
    author: str = ""
    
    # Status
    installed: bool = True
    outdated: bool = False
    latest_version: str = ""
    
    # Dates
    added_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Vulnerability:
    """Vulnerability."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cve_id: str = ""
    dependency_name: str = ""
    affected_versions: str = ""
    fixed_version: str = ""
    severity: VulnerabilitySeverity = VulnerabilitySeverity.MEDIUM
    title: str = ""
    description: str = ""
    cvss_score: float = 0.0
    published_at: Optional[datetime] = None
    references: List[str] = field(default_factory=list)


@dataclass
class DependencyUpdate:
    """Dependency update."""
    dependency_name: str = ""
    current_version: str = ""
    latest_version: str = ""
    update_type: UpdateType = UpdateType.PATCH
    breaking_changes: bool = False
    changelog_url: str = ""
    vulnerabilities_fixed: int = 0


@dataclass
class DependencyNode:
    """Dependency graph node."""
    name: str = ""
    version: str = ""
    depth: int = 0
    children: List[DependencyNode] = field(default_factory=list)


@dataclass
class DependencyStats:
    """Dependency statistics."""
    total: int = 0
    runtime: int = 0
    development: int = 0
    outdated: int = 0
    vulnerable: int = 0
    max_depth: int = 0


# Dependency store
class DependencyStore(ABC):
    """Dependency storage."""
    
    @abstractmethod
    async def save(self, dep: Dependency) -> None:
        pass
    
    @abstractmethod
    async def get(self, name: str) -> Optional[Dependency]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Dependency]:
        pass
    
    @abstractmethod
    async def delete(self, name: str) -> bool:
        pass


class InMemoryDependencyStore(DependencyStore):
    """In-memory dependency store."""
    
    def __init__(self):
        self._deps: Dict[str, Dependency] = {}
    
    async def save(self, dep: Dependency) -> None:
        self._deps[dep.name] = dep
    
    async def get(self, name: str) -> Optional[Dependency]:
        return self._deps.get(name)
    
    async def list_all(self) -> List[Dependency]:
        return list(self._deps.values())
    
    async def delete(self, name: str) -> bool:
        if name in self._deps:
            del self._deps[name]
            return True
        return False


# Vulnerability database
class VulnerabilityDB(ABC):
    """Vulnerability database."""
    
    @abstractmethod
    async def check(self, name: str, version: str) -> List[Vulnerability]:
        pass
    
    @abstractmethod
    async def add(self, vuln: Vulnerability) -> None:
        pass


class MockVulnerabilityDB(VulnerabilityDB):
    """Mock vulnerability database."""
    
    def __init__(self):
        self._vulns: Dict[str, List[Vulnerability]] = {}
    
    async def check(self, name: str, version: str) -> List[Vulnerability]:
        all_vulns = self._vulns.get(name, [])
        
        # Simple version check
        current = Version.parse(version)
        affected = []
        
        for vuln in all_vulns:
            fixed = Version.parse(vuln.fixed_version)
            if current < fixed:
                affected.append(vuln)
        
        return affected
    
    async def add(self, vuln: Vulnerability) -> None:
        if vuln.dependency_name not in self._vulns:
            self._vulns[vuln.dependency_name] = []
        self._vulns[vuln.dependency_name].append(vuln)


# Registry client
class RegistryClient(ABC):
    """Package registry client."""
    
    @abstractmethod
    async def get_latest_version(self, name: str) -> Optional[str]:
        pass
    
    @abstractmethod
    async def get_versions(self, name: str) -> List[str]:
        pass
    
    @abstractmethod
    async def get_metadata(self, name: str, version: str) -> Dict[str, Any]:
        pass


class MockRegistryClient(RegistryClient):
    """Mock registry client."""
    
    def __init__(self):
        self._packages: Dict[str, Dict[str, Any]] = {}
    
    async def get_latest_version(self, name: str) -> Optional[str]:
        pkg = self._packages.get(name)
        if pkg:
            return pkg.get("latest_version")
        return None
    
    async def get_versions(self, name: str) -> List[str]:
        pkg = self._packages.get(name)
        if pkg:
            return pkg.get("versions", [])
        return []
    
    async def get_metadata(self, name: str, version: str) -> Dict[str, Any]:
        pkg = self._packages.get(name)
        if pkg:
            return pkg.get("metadata", {})
        return {}
    
    def register_package(
        self,
        name: str,
        versions: List[str],
        metadata: Optional[Dict] = None,
    ) -> None:
        """Register package for testing."""
        self._packages[name] = {
            "versions": versions,
            "latest_version": versions[-1] if versions else None,
            "metadata": metadata or {},
        }


# Dependency manager
class DependencyManager:
    """Dependency manager."""
    
    def __init__(
        self,
        dep_store: Optional[DependencyStore] = None,
        vuln_db: Optional[VulnerabilityDB] = None,
        registry: Optional[RegistryClient] = None,
    ):
        self._dep_store = dep_store or InMemoryDependencyStore()
        self._vuln_db = vuln_db or MockVulnerabilityDB()
        self._registry = registry or MockRegistryClient()
        self._listeners: List[Callable] = []
    
    async def add(
        self,
        name: str,
        version: str,
        dep_type: Union[str, DependencyType] = DependencyType.RUNTIME,
        dependencies: Optional[List[str]] = None,
        **kwargs,
    ) -> Dependency:
        """Add dependency."""
        if isinstance(dep_type, str):
            dep_type = DependencyType(dep_type)
        
        dep = Dependency(
            name=name,
            version=version,
            dep_type=dep_type,
            dependencies=dependencies or [],
            **kwargs,
        )
        
        # Update dependents
        for child_name in dep.dependencies:
            child = await self._dep_store.get(child_name)
            if child:
                if name not in child.dependents:
                    child.dependents.append(name)
                await self._dep_store.save(child)
        
        await self._dep_store.save(dep)
        
        logger.info(f"Dependency added: {name}@{version}")
        
        await self._notify("add", dep)
        
        return dep
    
    async def get(self, name: str) -> Optional[Dependency]:
        """Get dependency."""
        return await self._dep_store.get(name)
    
    async def list_all(
        self,
        dep_type: Optional[DependencyType] = None,
    ) -> List[Dependency]:
        """List dependencies."""
        deps = await self._dep_store.list_all()
        
        if dep_type:
            deps = [d for d in deps if d.dep_type == dep_type]
        
        return deps
    
    async def remove(self, name: str) -> bool:
        """Remove dependency."""
        dep = await self._dep_store.get(name)
        
        if not dep:
            return False
        
        # Check dependents
        if dep.dependents:
            raise DependencyError(
                f"Cannot remove {name}: required by {', '.join(dep.dependents)}"
            )
        
        # Update children
        for child_name in dep.dependencies:
            child = await self._dep_store.get(child_name)
            if child and name in child.dependents:
                child.dependents.remove(name)
                await self._dep_store.save(child)
        
        result = await self._dep_store.delete(name)
        
        if result:
            logger.info(f"Dependency removed: {name}")
            await self._notify("remove", dep)
        
        return result
    
    async def update(
        self,
        name: str,
        version: str,
    ) -> Optional[Dependency]:
        """Update dependency version."""
        dep = await self._dep_store.get(name)
        
        if not dep:
            return None
        
        old_version = dep.version
        dep.version = version
        dep.updated_at = datetime.utcnow()
        dep.outdated = False
        
        await self._dep_store.save(dep)
        
        logger.info(f"Dependency updated: {name} {old_version} -> {version}")
        
        await self._notify("update", dep)
        
        return dep
    
    async def check_vulnerabilities(
        self,
        name: Optional[str] = None,
    ) -> List[Vulnerability]:
        """Check for vulnerabilities."""
        if name:
            dep = await self._dep_store.get(name)
            if not dep:
                return []
            deps = [dep]
        else:
            deps = await self._dep_store.list_all()
        
        all_vulns = []
        
        for dep in deps:
            vulns = await self._vuln_db.check(dep.name, dep.version)
            all_vulns.extend(vulns)
        
        return all_vulns
    
    async def check_updates(self) -> List[DependencyUpdate]:
        """Check for updates."""
        deps = await self._dep_store.list_all()
        updates = []
        
        for dep in deps:
            latest = await self._registry.get_latest_version(dep.name)
            
            if not latest:
                continue
            
            current = Version.parse(dep.version)
            new = Version.parse(latest)
            
            if new > current:
                # Determine update type
                if new.major > current.major:
                    update_type = UpdateType.MAJOR
                    breaking = True
                elif new.minor > current.minor:
                    update_type = UpdateType.MINOR
                    breaking = False
                else:
                    update_type = UpdateType.PATCH
                    breaking = False
                
                # Check vulnerabilities fixed
                current_vulns = await self._vuln_db.check(dep.name, dep.version)
                new_vulns = await self._vuln_db.check(dep.name, latest)
                vulns_fixed = len(current_vulns) - len(new_vulns)
                
                updates.append(DependencyUpdate(
                    dependency_name=dep.name,
                    current_version=dep.version,
                    latest_version=latest,
                    update_type=update_type,
                    breaking_changes=breaking,
                    vulnerabilities_fixed=max(0, vulns_fixed),
                ))
                
                # Mark as outdated
                dep.outdated = True
                dep.latest_version = latest
                await self._dep_store.save(dep)
        
        return updates
    
    async def get_dependency_graph(
        self,
        root: Optional[str] = None,
    ) -> DependencyNode:
        """Get dependency graph."""
        if root:
            dep = await self._dep_store.get(root)
            if not dep:
                return DependencyNode()
            return await self._build_node(dep, depth=0, visited=set())
        
        # Build root node with all top-level deps
        deps = await self._dep_store.list_all()
        root_deps = [d for d in deps if not d.dependents]
        
        root_node = DependencyNode(name="root", version="", depth=0)
        
        for dep in root_deps:
            child = await self._build_node(dep, depth=1, visited=set())
            root_node.children.append(child)
        
        return root_node
    
    async def _build_node(
        self,
        dep: Dependency,
        depth: int,
        visited: Set[str],
    ) -> DependencyNode:
        """Build dependency node recursively."""
        if dep.name in visited:
            # Circular dependency detected
            return DependencyNode(
                name=f"{dep.name} (circular)",
                version=dep.version,
                depth=depth,
            )
        
        visited.add(dep.name)
        
        node = DependencyNode(
            name=dep.name,
            version=dep.version,
            depth=depth,
        )
        
        for child_name in dep.dependencies:
            child = await self._dep_store.get(child_name)
            if child:
                child_node = await self._build_node(
                    child,
                    depth=depth + 1,
                    visited=visited.copy(),
                )
                node.children.append(child_node)
        
        return node
    
    async def detect_circular(self) -> List[List[str]]:
        """Detect circular dependencies."""
        deps = await self._dep_store.list_all()
        cycles = []
        
        for dep in deps:
            cycle = await self._find_cycle(dep.name, [], set())
            if cycle and cycle not in cycles:
                cycles.append(cycle)
        
        return cycles
    
    async def _find_cycle(
        self,
        name: str,
        path: List[str],
        visited: Set[str],
    ) -> Optional[List[str]]:
        """Find cycle starting from node."""
        if name in visited:
            if name in path:
                idx = path.index(name)
                return path[idx:] + [name]
            return None
        
        visited.add(name)
        path = path + [name]
        
        dep = await self._dep_store.get(name)
        if not dep:
            return None
        
        for child_name in dep.dependencies:
            cycle = await self._find_cycle(child_name, path, visited)
            if cycle:
                return cycle
        
        return None
    
    async def get_reverse_deps(self, name: str) -> List[Dependency]:
        """Get reverse dependencies (dependents)."""
        dep = await self._dep_store.get(name)
        
        if not dep:
            return []
        
        dependents = []
        
        for dependent_name in dep.dependents:
            dependent = await self._dep_store.get(dependent_name)
            if dependent:
                dependents.append(dependent)
        
        return dependents
    
    async def get_stats(self) -> DependencyStats:
        """Get dependency statistics."""
        deps = await self._dep_store.list_all()
        
        stats = DependencyStats(total=len(deps))
        
        for dep in deps:
            if dep.dep_type == DependencyType.RUNTIME:
                stats.runtime += 1
            elif dep.dep_type == DependencyType.DEVELOPMENT:
                stats.development += 1
            
            if dep.outdated:
                stats.outdated += 1
        
        # Check vulnerabilities
        vulns = await self.check_vulnerabilities()
        vulnerable_deps = set(v.dependency_name for v in vulns)
        stats.vulnerable = len(vulnerable_deps)
        
        # Calculate max depth
        graph = await self.get_dependency_graph()
        stats.max_depth = self._calculate_depth(graph)
        
        return stats
    
    def _calculate_depth(self, node: DependencyNode) -> int:
        """Calculate maximum depth."""
        if not node.children:
            return node.depth
        
        return max(self._calculate_depth(child) for child in node.children)
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
    async def _notify(self, event: str, dep: Dependency) -> None:
        """Notify listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, dep)
                else:
                    listener(event, dep)
            except Exception as e:
                logger.error(f"Listener error: {e}")


# Factory functions
def create_dependency_manager() -> DependencyManager:
    """Create dependency manager."""
    return DependencyManager()


def create_dependency(
    name: str,
    version: str,
    **kwargs,
) -> Dependency:
    """Create dependency."""
    return Dependency(name=name, version=version, **kwargs)


def parse_version(version_str: str) -> Version:
    """Parse version string."""
    return Version.parse(version_str)


__all__ = [
    # Exceptions
    "DependencyError",
    "CircularDependencyError",
    "VersionConflictError",
    # Enums
    "DependencyType",
    "VulnerabilitySeverity",
    "UpdateType",
    # Data classes
    "Version",
    "Dependency",
    "Vulnerability",
    "DependencyUpdate",
    "DependencyNode",
    "DependencyStats",
    # Stores
    "DependencyStore",
    "InMemoryDependencyStore",
    "VulnerabilityDB",
    "MockVulnerabilityDB",
    "RegistryClient",
    "MockRegistryClient",
    # Manager
    "DependencyManager",
    # Factory functions
    "create_dependency_manager",
    "create_dependency",
    "parse_version",
]
