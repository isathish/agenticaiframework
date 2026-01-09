"""
Comprehensive tests for prompt versioning module.

Tests for:
- PromptLibrary
- PromptVersionManager
- PromptVersion and related types
"""

import pytest
import time
import uuid


class TestPromptLibrary:
    """Tests for PromptLibrary."""
    
    def test_init(self):
        """Test library initialization."""
        from agenticaiframework.prompt_versioning.library import PromptLibrary
        
        library = PromptLibrary()
        assert library.components == {}
        assert library.categories == {}
    
    def test_register_component(self):
        """Test registering component."""
        from agenticaiframework.prompt_versioning.library import PromptLibrary
        
        library = PromptLibrary()
        
        library.register_component(
            name="greeting",
            content="Hello, {name}!",
            category="basic",
            description="Basic greeting"
        )
        
        assert "greeting" in library.components
        assert "basic" in library.categories
    
    def test_compose_components(self):
        """Test composing multiple components."""
        from agenticaiframework.prompt_versioning.library import PromptLibrary
        
        library = PromptLibrary()
        
        library.register_component("intro", "Introduction paragraph")
        library.register_component("body", "Main content")
        library.register_component("outro", "Conclusion")
        
        result = library.compose(["intro", "body", "outro"])
        
        assert "Introduction paragraph" in result
        assert "Main content" in result
        assert "Conclusion" in result
    
    def test_compose_missing_component(self):
        """Test compose with missing component."""
        from agenticaiframework.prompt_versioning.library import PromptLibrary
        
        library = PromptLibrary()
        library.register_component("intro", "Introduction")
        
        result = library.compose(["intro", "missing"])
        
        # Should only contain the existing component
        assert "Introduction" in result
    
    def test_extend_component(self):
        """Test extending component."""
        from agenticaiframework.prompt_versioning.library import PromptLibrary
        
        library = PromptLibrary()
        library.register_component("base", "Base content")
        
        result = library.extend(
            base_component="base",
            extensions={'prefix': 'PREFIX: ', 'suffix': ' :SUFFIX'}
        )
        
        assert result is not None
    
    def test_extend_nonexistent(self):
        """Test extending nonexistent component raises error."""
        from agenticaiframework.prompt_versioning.library import PromptLibrary
        
        library = PromptLibrary()
        
        with pytest.raises(ValueError):
            library.extend("nonexistent", {})
    
    def test_get_by_category(self):
        """Test getting components by category."""
        from agenticaiframework.prompt_versioning.library import PromptLibrary
        
        library = PromptLibrary()
        
        library.register_component("a", "Content A", category="cat1")
        library.register_component("b", "Content B", category="cat1")
        library.register_component("c", "Content C", category="cat2")
        
        cat1_components = library.categories.get("cat1", [])
        assert len(cat1_components) == 2


class TestPromptVersionManager:
    """Tests for PromptVersionManager."""
    
    def test_init(self):
        """Test manager initialization."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        
        manager = PromptVersionManager()
        assert manager.prompts == {}
        assert manager.active_versions == {}
    
    def test_create_prompt(self):
        """Test creating a new prompt."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        
        manager = PromptVersionManager()
        
        version = manager.create_prompt(
            name="greeting",
            template="Hello, {name}!",
            created_by="test"
        )
        
        assert version.name == "greeting"
        assert version.version == "1.0.0"
        assert "name" in version.variables
    
    def test_create_with_variables(self):
        """Test creating prompt with explicit variables."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        
        manager = PromptVersionManager()
        
        version = manager.create_prompt(
            name="test",
            template="Test {var1} and {var2}",
            variables=["var1", "var2", "var3"]
        )
        
        assert "var1" in version.variables
        assert "var3" in version.variables
    
    def test_create_with_tags(self):
        """Test creating prompt with tags."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        
        manager = PromptVersionManager()
        
        version = manager.create_prompt(
            name="test",
            template="Test content",
            tags=["greeting", "formal"]
        )
        
        assert "greeting" in version.tags
    
    def test_create_version(self):
        """Test creating a new version of prompt."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        
        manager = PromptVersionManager()
        
        # Create initial version
        v1 = manager.create_prompt(
            name="greeting",
            template="Hello, {name}!"
        )
        
        # Create new version
        v2 = manager.create_version(
            v1.prompt_id,
            template="Hi there, {name}!",
            version_bump="minor"
        )
        
        assert v2.version == "1.1.0"
        assert v2.parent_version == "1.0.0"
    
    def test_create_version_major(self):
        """Test creating major version bump."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        
        manager = PromptVersionManager()
        
        v1 = manager.create_prompt(name="test", template="Test")
        v2 = manager.create_version(v1.prompt_id, template="New test", version_bump="major")
        
        assert v2.version == "2.0.0"
    
    def test_get_prompt(self):
        """Test getting prompt by ID."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        
        manager = PromptVersionManager()
        
        version = manager.create_prompt(
            name="test",
            template="Test content"
        )
        
        retrieved = manager.get_prompt(version.prompt_id)
        assert retrieved is not None
        assert retrieved.name == "test"
    
    def test_get_prompt_specific_version(self):
        """Test getting specific version."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        
        manager = PromptVersionManager()
        
        v1 = manager.create_prompt(name="test", template="Version 1")
        v2 = manager.create_version(v1.prompt_id, template="Version 2")
        
        # Get specific version
        retrieved = manager.get_prompt(v1.prompt_id, "1.0.0")
        assert retrieved.template == "Version 1"
    
    def test_get_prompt_not_found(self):
        """Test getting nonexistent prompt."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        
        manager = PromptVersionManager()
        
        result = manager.get_prompt("nonexistent")
        assert result is None
    
    def test_activate_prompt(self):
        """Test activating a prompt version."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        from agenticaiframework.prompt_versioning.types import PromptStatus
        
        manager = PromptVersionManager()
        
        version = manager.create_prompt(
            name="test",
            template="Test content"
        )
        
        manager.activate(version.prompt_id, version.version)
        
        prompt = manager.get_prompt(version.prompt_id, version.version)
        assert prompt.status == PromptStatus.ACTIVE
    
    def test_deprecate_prompt(self):
        """Test deprecating a prompt version."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        from agenticaiframework.prompt_versioning.types import PromptStatus
        
        manager = PromptVersionManager()
        
        version = manager.create_prompt(
            name="test",
            template="Test content"
        )
        
        manager.activate(version.prompt_id, version.version)
        manager.deprecate(version.prompt_id, version.version)
        
        prompt = manager.get_prompt(version.prompt_id, version.version)
        assert prompt.status == PromptStatus.DEPRECATED


class TestPromptVersionTypes:
    """Tests for prompt versioning types."""
    
    def test_prompt_status_enum(self):
        """Test PromptStatus enum."""
        from agenticaiframework.prompt_versioning.types import PromptStatus
        
        assert PromptStatus.DRAFT.value == "draft"
        assert PromptStatus.ACTIVE.value == "active"
        assert PromptStatus.DEPRECATED.value == "deprecated"
    
    def test_prompt_version_dataclass(self):
        """Test PromptVersion dataclass."""
        from agenticaiframework.prompt_versioning.types import PromptVersion, PromptStatus
        
        version = PromptVersion(
            prompt_id="p1",
            version="1.0.0",
            name="test",
            template="Test {var}",
            variables=["var"],
            status=PromptStatus.DRAFT,
            created_at=time.time(),
            created_by="test"
        )
        
        assert version.prompt_id == "p1"
        assert version.version == "1.0.0"
    
    def test_prompt_version_content_hash(self):
        """Test PromptVersion content_hash property."""
        from agenticaiframework.prompt_versioning.types import PromptVersion, PromptStatus
        
        version = PromptVersion(
            prompt_id="p1",
            version="1.0.0",
            name="test",
            template="Test content",
            variables=[],
            status=PromptStatus.DRAFT,
            created_at=time.time(),
            created_by="test"
        )
        
        assert len(version.content_hash) == 12
    
    def test_prompt_version_to_dict(self):
        """Test PromptVersion to_dict method."""
        from agenticaiframework.prompt_versioning.types import PromptVersion, PromptStatus
        
        version = PromptVersion(
            prompt_id="p1",
            version="1.0.0",
            name="test",
            template="Test",
            variables=[],
            status=PromptStatus.DRAFT,
            created_at=time.time(),
            created_by="test"
        )
        
        d = version.to_dict()
        assert d['prompt_id'] == "p1"
        assert d['status'] == "draft"
    
    def test_prompt_audit_entry(self):
        """Test PromptAuditEntry dataclass."""
        from agenticaiframework.prompt_versioning.types import PromptAuditEntry
        
        entry = PromptAuditEntry(
            entry_id=str(uuid.uuid4()),
            prompt_id="p1",
            version="1.0.0",
            action="created",
            actor="test",
            timestamp=time.time()
        )
        
        assert entry.action == "created"


class TestPromptVersioningIntegration:
    """Integration tests for prompt versioning."""
    
    def test_library_with_manager(self):
        """Test using library with version manager."""
        from agenticaiframework.prompt_versioning.library import PromptLibrary
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        
        library = PromptLibrary()
        manager = PromptVersionManager()
        
        # Register component
        library.register_component("greeting", "Hello, {name}!")
        
        # Create versioned prompt from component
        component_content = library.components["greeting"]["content"]
        version = manager.create_prompt(
            name="greeting_v1",
            template=component_content
        )
        
        assert version.name == "greeting_v1"
    
    def test_version_workflow(self):
        """Test complete version workflow."""
        from agenticaiframework.prompt_versioning.manager import PromptVersionManager
        from agenticaiframework.prompt_versioning.types import PromptStatus
        
        manager = PromptVersionManager()
        
        # Create
        v1 = manager.create_prompt(
            name="workflow_test",
            template="Version 1: {content}"
        )
        assert v1.status == PromptStatus.DRAFT
        
        # Activate
        manager.activate(v1.prompt_id, v1.version)
        v1_updated = manager.get_prompt(v1.prompt_id, v1.version)
        assert v1_updated.status == PromptStatus.ACTIVE
        
        # Create new version
        v2 = manager.create_version(
            v1.prompt_id,
            template="Version 2: {content}",
            version_bump="major"
        )
        assert v2.version == "2.0.0"
