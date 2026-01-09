"""
Tests for tasks module.
"""

import pytest
from unittest.mock import Mock, patch

from agenticaiframework.tasks import Task, TaskManager


class TestTask:
    """Tests for Task class."""
    
    def test_init(self):
        """Test Task initialization."""
        executor = Mock(return_value="result")
        task = Task(
            name="test_task",
            objective="Do something",
            executor=executor
        )
        
        assert task.name == "test_task"
        assert task.objective == "Do something"
        assert task.status == "pending"
        assert task.result is None
        assert task.id is not None
    
    def test_init_with_inputs(self):
        """Test Task initialization with inputs."""
        executor = Mock()
        task = Task(
            name="test_task",
            objective="Do something",
            executor=executor,
            inputs={"key": "value"}
        )
        
        assert task.inputs == {"key": "value"}
    
    def test_run_success(self):
        """Test successful task execution."""
        executor = Mock(return_value="success")
        task = Task(
            name="test_task",
            objective="Do something",
            executor=executor
        )
        
        result = task.run()
        
        assert result == "success"
        assert task.status == "completed"
        assert task.result == "success"
        executor.assert_called_once()
    
    def test_run_with_inputs(self):
        """Test task execution with inputs."""
        executor = Mock(return_value="result")
        task = Task(
            name="test_task",
            objective="Do something",
            executor=executor,
            inputs={"x": 1, "y": 2}
        )
        
        task.run()
        
        executor.assert_called_once_with(x=1, y=2)
    
    def test_run_failure(self):
        """Test task execution failure."""
        executor = Mock(side_effect=ValueError("test error"))
        task = Task(
            name="test_task",
            objective="Do something",
            executor=executor
        )
        
        task.run()
        
        assert task.status == "failed"
    
    def test_run_type_error(self):
        """Test task execution with TypeError."""
        executor = Mock(side_effect=TypeError("type error"))
        task = Task(
            name="test_task",
            objective="Do something",
            executor=executor
        )
        
        task.run()
        
        assert task.status == "failed"
    
    def test_run_key_error(self):
        """Test task execution with KeyError."""
        executor = Mock(side_effect=KeyError("key error"))
        task = Task(
            name="test_task",
            objective="Do something",
            executor=executor
        )
        
        task.run()
        
        assert task.status == "failed"
    
    def test_run_unexpected_error(self):
        """Test task execution with unexpected error."""
        executor = Mock(side_effect=RuntimeError("unexpected"))
        task = Task(
            name="test_task",
            objective="Do something",
            executor=executor
        )
        
        task.run()
        
        assert task.status == "failed"
    
    def test_version_default(self):
        """Test default version."""
        task = Task(
            name="test_task",
            objective="Do something",
            executor=Mock()
        )
        
        assert task.version == "1.0.0"


class TestTaskManager:
    """Tests for TaskManager class."""
    
    def test_init(self):
        """Test TaskManager initialization."""
        manager = TaskManager()
        assert len(manager.tasks) == 0
    
    def test_register_task(self):
        """Test registering a task."""
        manager = TaskManager()
        task = Task(
            name="test_task",
            objective="Do something",
            executor=Mock()
        )
        
        manager.register_task(task)
        
        assert task.id in manager.tasks
        assert manager.tasks[task.id] == task
    
    def test_get_task(self):
        """Test getting a task by ID."""
        manager = TaskManager()
        task = Task(
            name="test_task",
            objective="Do something",
            executor=Mock()
        )
        manager.register_task(task)
        
        retrieved = manager.get_task(task.id)
        
        assert retrieved == task
    
    def test_get_task_not_found(self):
        """Test getting nonexistent task."""
        manager = TaskManager()
        
        result = manager.get_task("nonexistent")
        
        assert result is None
    
    def test_list_tasks(self):
        """Test listing all tasks."""
        manager = TaskManager()
        task1 = Task("task1", "obj1", Mock())
        task2 = Task("task2", "obj2", Mock())
        
        manager.register_task(task1)
        manager.register_task(task2)
        
        tasks = manager.list_tasks()
        
        assert len(tasks) == 2
        assert task1 in tasks
        assert task2 in tasks
    
    def test_remove_task(self):
        """Test removing a task."""
        manager = TaskManager()
        task = Task("test_task", "objective", Mock())
        manager.register_task(task)
        
        manager.remove_task(task.id)
        
        assert task.id not in manager.tasks
    
    def test_remove_task_not_found(self):
        """Test removing nonexistent task."""
        manager = TaskManager()
        
        # Should not raise
        manager.remove_task("nonexistent")
    
    def test_run_all(self):
        """Test running all tasks."""
        manager = TaskManager()
        
        executor1 = Mock(return_value="result1")
        executor2 = Mock(return_value="result2")
        
        task1 = Task("task1", "obj1", executor1)
        task2 = Task("task2", "obj2", executor2)
        
        manager.register_task(task1)
        manager.register_task(task2)
        
        results = manager.run_all()
        
        assert results[task1.id] == "result1"
        assert results[task2.id] == "result2"
        executor1.assert_called_once()
        executor2.assert_called_once()
    
    def test_execute_task_by_id(self):
        """Test executing task by ID."""
        manager = TaskManager()
        executor = Mock(return_value="result")
        task = Task("test_task", "objective", executor)
        manager.register_task(task)
        
        result = manager.execute_task(task.id)
        
        assert result == "result"
    
    def test_execute_task_by_name(self):
        """Test executing task by name."""
        manager = TaskManager()
        executor = Mock(return_value="result")
        task = Task("unique_name", "objective", executor)
        manager.register_task(task)
        
        result = manager.execute_task("unique_name")
        
        assert result == "result"
    
    def test_execute_task_not_found(self):
        """Test executing nonexistent task."""
        manager = TaskManager()
        
        result = manager.execute_task("nonexistent")
        
        assert result is None


class TestTaskIntegration:
    """Integration tests for Task and TaskManager."""
    
    def test_register_and_run_multiple(self):
        """Test registering and running multiple tasks."""
        manager = TaskManager()
        
        results_list = []
        
        def task_fn(value):
            results_list.append(value)
            return value * 2
        
        for i in range(5):
            task = Task(f"task_{i}", f"objective_{i}", task_fn, {"value": i})
            manager.register_task(task)
        
        results = manager.run_all()
        
        assert len(results) == 5
        assert results_list == [0, 1, 2, 3, 4]
    
    def test_task_status_transitions(self):
        """Test task status transitions."""
        executor = Mock(return_value="result")
        task = Task("test", "obj", executor)
        
        assert task.status == "pending"
        
        task.run()
        
        assert task.status == "completed"
