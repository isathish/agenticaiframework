# AgenticAI Framework Tests

Comprehensive test suite organized by type.

## 📁 Directory Structure

```
tests/
├── unit/            # Unit tests for individual components
├── integration/     # Integration tests for component interaction
├── coverage/        # Coverage analysis tests
├── test_import.py   # Package import validation
└── test_tools_import.py  # Tools framework import validation
```

## 🧪 Running Tests

### Run All Tests
```bash
python -m pytest tests/ -v
```

### Run by Category
```bash
# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests only
python -m pytest tests/integration/ -v

# Coverage tests
python -m pytest tests/coverage/ -v
```

### Run Specific Test File
```bash
python -m pytest tests/unit/test_tools.py -v
```

### Run with Coverage Report
```bash
python -m pytest tests/ --cov=agenticaiframework --cov-report=html -v
```

## 📚 Test Categories

### Unit Tests (`unit/`)
- `test_agents.py` - Agent creation, lifecycle, hooks
- `test_communication.py` - Agent communication protocols
- `test_exceptions.py` - Exception handling
- `test_knowledge.py` - Knowledge storage and retrieval
- `test_memory.py` - Memory operations
- `test_prompts.py` - Prompt templates and rendering
- `test_tools.py` - **Complete tools framework tests** (42 tests)
  - BaseTool and AsyncBaseTool
  - ToolRegistry
  - ToolExecutor
  - AgentToolManager
  - MCP compatibility

### Integration Tests (`integration/`)
- `test_integrations.py` - External service integration
- `test_monitoring.py` - Monitoring and metrics
- `test_tasks.py` - Task orchestration

### Coverage Tests (`coverage/`)
- Tests for ensuring high code coverage across modules

## ✅ Test Summary

| Category | Files | Tests | Status |
|----------|-------|-------|--------|
| Unit | 7 | ~200 | ✅ |
| Integration | 3 | ~50 | ✅ |
| Coverage | 7 | ~200 | ✅ |
| Import | 2 | ~25 | ✅ |
| **Total** | **19** | **~475** | **✅** |

## 🔧 Test Markers

```bash
# Run tests by marker
python -m pytest -m "slow" tests/  # Long-running tests
python -m pytest -m "not slow" tests/  # Quick tests
```

## 💡 Writing New Tests

1. Place unit tests in `tests/unit/`
2. Place integration tests in `tests/integration/`
3. Follow naming convention: `test_<module>.py`
4. Use descriptive test class and method names
5. Include docstrings for complex tests

Example:
```python
class TestMyFeature:
    """Tests for MyFeature class."""
    
    def test_basic_functionality(self):
        """Test that basic functionality works."""
        feature = MyFeature()
        result = feature.do_something()
        assert result is not None
```
