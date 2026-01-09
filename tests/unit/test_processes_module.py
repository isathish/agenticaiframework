"""
Tests for processes module.
"""

import time
import pytest
from unittest.mock import Mock, patch

from agenticaiframework.processes import Process


class TestProcess:
    """Tests for Process class."""
    
    def test_init_default(self):
        """Test default initialization."""
        process = Process(name="test_process")
        
        assert process.name == "test_process"
        assert process.strategy == "sequential"
        assert len(process.tasks) == 0
        assert process.status == "initialized"
    
    def test_init_with_strategy(self):
        """Test initialization with strategy."""
        process = Process(name="test_process", strategy="parallel")
        
        assert process.strategy == "parallel"
    
    def test_add_task(self):
        """Test adding a task."""
        process = Process(name="test_process")
        task_fn = Mock(__name__="test_task")
        
        process.add_task(task_fn, 1, 2, key="value")
        
        assert len(process.tasks) == 1
        assert process.tasks[0] == (task_fn, (1, 2), {"key": "value"})
    
    def test_add_step_alias(self):
        """Test add_step is alias for add_task."""
        process = Process(name="test_process")
        step_fn = Mock(__name__="test_step")
        
        process.add_step(step_fn, "arg")
        
        assert len(process.tasks) == 1
    
    def test_execute_sequential(self):
        """Test sequential execution."""
        process = Process(name="test_process", strategy="sequential")
        
        call_order = []
        
        def task1():
            call_order.append(1)
            return "result1"
        
        def task2():
            call_order.append(2)
            return "result2"
        
        task1.__name__ = "task1"
        task2.__name__ = "task2"
        
        process.add_task(task1)
        process.add_task(task2)
        
        results = process.execute()
        
        assert results == ["result1", "result2"]
        assert call_order == [1, 2]
        assert process.status == "completed"
    
    def test_execute_parallel(self):
        """Test parallel execution."""
        process = Process(name="test_process", strategy="parallel")
        
        results_list = []
        
        def task1():
            results_list.append(1)
            return "result1"
        
        def task2():
            results_list.append(2)
            return "result2"
        
        task1.__name__ = "task1"
        task2.__name__ = "task2"
        
        process.add_task(task1)
        process.add_task(task2)
        
        results = process.execute()
        
        assert len(results) == 2
        assert "result1" in results
        assert "result2" in results
        assert process.status == "completed"
    
    def test_execute_hybrid(self):
        """Test hybrid execution."""
        process = Process(name="test_process", strategy="hybrid")
        
        def task1():
            return "result1"
        
        def task2():
            return "result2"
        
        def task3():
            return "result3"
        
        def task4():
            return "result4"
        
        task1.__name__ = "task1"
        task2.__name__ = "task2"
        task3.__name__ = "task3"
        task4.__name__ = "task4"
        
        process.add_task(task1)
        process.add_task(task2)
        process.add_task(task3)
        process.add_task(task4)
        
        results = process.execute()
        
        assert len(results) == 4
        assert process.status == "completed"
    
    def test_execute_with_args(self):
        """Test execution with arguments."""
        process = Process(name="test_process")
        
        def add(a, b):
            return a + b
        
        add.__name__ = "add"
        
        process.add_task(add, 1, 2)
        
        results = process.execute()
        
        assert results == [3]
    
    def test_execute_with_kwargs(self):
        """Test execution with keyword arguments."""
        process = Process(name="test_process")
        
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"
        
        greet.__name__ = "greet"
        
        process.add_task(greet, name="World", greeting="Hi")
        
        results = process.execute()
        
        assert results == ["Hi, World!"]
    
    def test_execute_empty_process(self):
        """Test execution with no tasks."""
        process = Process(name="empty_process")
        
        results = process.execute()
        
        assert results == []
        assert process.status == "completed"
    
    def test_status_transitions(self):
        """Test status transitions during execution."""
        process = Process(name="test_process")
        
        def slow_task():
            time.sleep(0.01)
            return "done"
        
        slow_task.__name__ = "slow_task"
        
        process.add_task(slow_task)
        
        assert process.status == "initialized"
        
        process.execute()
        
        assert process.status == "completed"


class TestProcessStrategies:
    """Tests for different process strategies."""
    
    def test_sequential_maintains_order(self):
        """Test sequential execution maintains order."""
        process = Process(name="test", strategy="sequential")
        
        results = []
        
        def task(n):
            results.append(n)
            return n
        
        task.__name__ = "task"
        
        for i in range(5):
            process.add_task(task, i)
        
        process.execute()
        
        assert results == [0, 1, 2, 3, 4]
    
    def test_parallel_completes_all(self):
        """Test parallel execution completes all tasks."""
        process = Process(name="test", strategy="parallel")
        
        completed = []
        
        def task(n):
            time.sleep(0.01)
            completed.append(n)
            return n
        
        task.__name__ = "task"
        
        for i in range(5):
            process.add_task(task, i)
        
        process.execute()
        
        assert set(completed) == {0, 1, 2, 3, 4}
    
    def test_hybrid_split_behavior(self):
        """Test hybrid strategy splits tasks correctly."""
        process = Process(name="test", strategy="hybrid")
        
        # 6 tasks: first 3 sequential, last 3 parallel
        for i in range(6):
            fn = lambda x=i: x
            fn.__name__ = f"task_{i}"
            process.add_task(fn)
        
        results = process.execute()
        
        assert len(results) == 6


class TestProcessEdgeCases:
    """Edge case tests for Process."""
    
    def test_single_task(self):
        """Test with single task."""
        process = Process(name="single")
        
        def task():
            return "result"
        
        task.__name__ = "task"
        
        process.add_task(task)
        
        results = process.execute()
        
        assert results == ["result"]
    
    def test_task_with_exception(self):
        """Test task that raises exception."""
        process = Process(name="test")
        
        def failing_task():
            raise ValueError("test error")
        
        failing_task.__name__ = "failing_task"
        
        process.add_task(failing_task)
        
        with pytest.raises(ValueError):
            process.execute()
    
    def test_parallel_task_with_exception(self):
        """Test parallel task that raises exception."""
        process = Process(name="test", strategy="parallel")
        
        def failing_task():
            raise ValueError("test error")
        
        failing_task.__name__ = "failing_task"
        
        process.add_task(failing_task)
        
        with pytest.raises(ValueError):
            process.execute()
