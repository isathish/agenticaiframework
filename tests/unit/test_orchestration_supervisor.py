"""
Tests for orchestration/supervisor.py - Agent Supervisor.
"""

import time
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from agenticaiframework.orchestration.supervisor import AgentSupervisor
from agenticaiframework.orchestration.types import (
    SupervisionStrategy,
    AgentRole,
    AgentState,
)
from agenticaiframework.orchestration.models import (
    SupervisionConfig,
    TaskAssignment,
    AgentHandoff,
)


class MockAgent:
    """Mock agent for testing."""
    
    def __init__(self, name="test_agent", agent_id=None, capabilities=None):
        self.id = agent_id or f"agent-{name}"
        self.name = name
        self.capabilities = capabilities or []
        self.role = AgentRole.WORKER
        self.supervisor_id = None
        self._status = "idle"
    
    def stop(self):
        self._status = "stopped"
    
    def get_performance_metrics(self):
        return {'success_rate': 0.8, 'total_tasks': 5}
    
    def execute_task(self, task_callable, *args, **kwargs):
        """Execute a task callable."""
        return task_callable(*args, **kwargs)


class TestAgentSupervisor:
    """Tests for AgentSupervisor class."""
    
    def test_init_default(self):
        """Test default initialization."""
        supervisor = AgentSupervisor(name="test_supervisor")
        
        assert supervisor.name == "test_supervisor"
        assert supervisor.id is not None
        assert supervisor.config is not None
        assert supervisor.parent_supervisor is None
        assert len(supervisor.agents) == 0
        assert supervisor.status == "running"
    
    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = SupervisionConfig(
            strategy=SupervisionStrategy.REST_FOR_ONE,
            max_restarts=5,
            restart_window=120
        )
        
        supervisor = AgentSupervisor(name="test", config=config)
        
        assert supervisor.config.strategy == SupervisionStrategy.REST_FOR_ONE
        assert supervisor.config.max_restarts == 5
    
    def test_init_with_parent(self):
        """Test initialization with parent supervisor."""
        parent = AgentSupervisor(name="parent")
        child = AgentSupervisor(name="child", parent_supervisor=parent)
        
        assert child.parent_supervisor == parent
    
    def test_add_agent(self):
        """Test adding an agent."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker1")
        
        supervisor.add_agent(agent)
        
        assert agent.id in supervisor.agents
        assert supervisor.agent_states[agent.id] == AgentState.IDLE
        assert agent.supervisor_id == supervisor.id
    
    def test_add_agent_with_role(self):
        """Test adding agent with specific role."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="specialist")
        
        supervisor.add_agent(agent, role=AgentRole.SPECIALIST)
        
        assert agent.role == AgentRole.SPECIALIST
    
    def test_remove_agent(self):
        """Test removing an agent."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker")
        
        supervisor.add_agent(agent)
        supervisor.remove_agent(agent.id)
        
        assert agent.id not in supervisor.agents
        assert agent.id not in supervisor.agent_states
        assert agent._status == "stopped"
    
    def test_remove_nonexistent_agent(self):
        """Test removing agent that doesn't exist."""
        supervisor = AgentSupervisor(name="test")
        
        # Should not raise
        supervisor.remove_agent("nonexistent-id")
    
    def test_add_child_supervisor(self):
        """Test adding a child supervisor."""
        parent = AgentSupervisor(name="parent")
        child = AgentSupervisor(name="child")
        
        parent.add_child_supervisor(child)
        
        assert child.id in parent.child_supervisors
        assert child.parent_supervisor == parent
    
    def test_get_all_agents_single_level(self):
        """Test getting all agents without recursion."""
        supervisor = AgentSupervisor(name="test")
        
        agent1 = MockAgent(name="agent1")
        agent2 = MockAgent(name="agent2")
        
        supervisor.add_agent(agent1)
        supervisor.add_agent(agent2)
        
        agents = supervisor.get_all_agents(recursive=False)
        
        assert len(agents) == 2
    
    def test_get_all_agents_recursive(self):
        """Test getting all agents recursively."""
        parent = AgentSupervisor(name="parent")
        child = AgentSupervisor(name="child")
        
        parent.add_child_supervisor(child)
        
        agent1 = MockAgent(name="parent_agent")
        agent2 = MockAgent(name="child_agent")
        
        parent.add_agent(agent1)
        child.add_agent(agent2)
        
        agents = parent.get_all_agents(recursive=True)
        
        assert len(agents) == 2
    
    def test_get_available_agents(self):
        """Test getting available agents."""
        supervisor = AgentSupervisor(name="test")
        
        agent1 = MockAgent(name="agent1")
        agent2 = MockAgent(name="agent2")
        
        supervisor.add_agent(agent1)
        supervisor.add_agent(agent2)
        
        # Both should be idle/available
        available = supervisor.get_available_agents()
        
        assert len(available) == 2
    
    def test_get_available_agents_with_capability(self):
        """Test getting available agents with specific capability."""
        supervisor = AgentSupervisor(name="test")
        
        agent1 = MockAgent(name="agent1", capabilities=["coding"])
        agent2 = MockAgent(name="agent2", capabilities=["writing"])
        
        supervisor.add_agent(agent1)
        supervisor.add_agent(agent2)
        
        available = supervisor.get_available_agents(capability="coding")
        
        assert len(available) == 1
        assert available[0].name == "agent1"
    
    def test_get_available_agents_busy(self):
        """Test that busy agents are not returned."""
        supervisor = AgentSupervisor(name="test")
        
        agent = MockAgent(name="agent1")
        supervisor.add_agent(agent)
        
        # Mark agent as busy
        supervisor.agent_states[agent.id] = AgentState.BUSY
        
        available = supervisor.get_available_agents()
        
        assert len(available) == 0


class TestTaskDelegation:
    """Tests for task delegation functionality."""
    
    def test_delegate_task_to_available_agent(self):
        """Test delegating task to an available agent."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker")
        supervisor.add_agent(agent)
        
        def sample_task():
            return "done"
        
        task_id = supervisor.delegate_task(sample_task)
        
        assert task_id is not None
        assert supervisor.metrics['tasks_delegated'] == 1
    
    def test_delegate_task_no_agents(self):
        """Test delegating task when no agents available."""
        supervisor = AgentSupervisor(name="test")
        
        def sample_task():
            return "done"
        
        task_id = supervisor.delegate_task(sample_task)
        
        assert task_id is not None
        assert len(supervisor.task_queue) == 1
    
    def test_delegate_task_with_args(self):
        """Test delegating task with arguments."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker")
        supervisor.add_agent(agent)
        
        def add(a, b):
            return a + b
        
        task_id = supervisor.delegate_task(add, args=(1, 2))
        
        assert task_id is not None
    
    def test_delegate_task_with_kwargs(self):
        """Test delegating task with keyword arguments."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker")
        supervisor.add_agent(agent)
        
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"
        
        task_id = supervisor.delegate_task(greet, kwargs={"name": "World"})
        
        assert task_id is not None
    
    def test_delegate_task_with_priority(self):
        """Test task delegation with priority."""
        supervisor = AgentSupervisor(name="test")
        # No agents - tasks go to queue
        
        def task1():
            pass
        
        def task2():
            pass
        
        supervisor.delegate_task(task1, priority=1)
        supervisor.delegate_task(task2, priority=10)
        
        # Higher priority should be first
        assert supervisor.task_queue[0].priority == 10
    
    def test_delegate_task_with_deadline(self):
        """Test task delegation with deadline."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker")
        supervisor.add_agent(agent)
        
        deadline = datetime.now()
        
        def task():
            pass
        
        task_id = supervisor.delegate_task(task, deadline=deadline)
        
        assert task_id is not None
    
    def test_delegate_task_preferred_agent(self):
        """Test delegating task to preferred agent."""
        supervisor = AgentSupervisor(name="test")
        
        agent1 = MockAgent(name="agent1", agent_id="agent-1")
        agent2 = MockAgent(name="agent2", agent_id="agent-2")
        
        supervisor.add_agent(agent1)
        supervisor.add_agent(agent2)
        
        def task():
            pass
        
        task_id = supervisor.delegate_task(task, preferred_agent_id="agent-2")
        
        assert task_id is not None
    
    def test_select_agent_from_child_supervisor(self):
        """Test agent selection from child supervisor."""
        parent = AgentSupervisor(name="parent")
        child = AgentSupervisor(name="child")
        
        parent.add_child_supervisor(child)
        
        agent = MockAgent(name="child_agent", capabilities=["special"])
        child.add_agent(agent)
        
        # Parent has no agents with capability
        available = parent.get_available_agents(capability="special")
        
        # Direct call doesn't search children
        assert len(available) == 0


class TestSupervisionStrategies:
    """Tests for supervision strategies."""
    
    def test_one_for_one_strategy(self):
        """Test one-for-one supervision strategy."""
        config = SupervisionConfig(strategy=SupervisionStrategy.ONE_FOR_ONE)
        supervisor = AgentSupervisor(name="test", config=config)
        
        assert supervisor.config.strategy == SupervisionStrategy.ONE_FOR_ONE
    
    def test_one_for_all_strategy(self):
        """Test one-for-all supervision strategy."""
        config = SupervisionConfig(strategy=SupervisionStrategy.ONE_FOR_ALL)
        supervisor = AgentSupervisor(name="test", config=config)
        
        assert supervisor.config.strategy == SupervisionStrategy.ONE_FOR_ALL
    
    def test_rest_for_one_strategy(self):
        """Test rest-for-one supervision strategy."""
        config = SupervisionConfig(strategy=SupervisionStrategy.REST_FOR_ONE)
        supervisor = AgentSupervisor(name="test", config=config)
        
        assert supervisor.config.strategy == SupervisionStrategy.REST_FOR_ONE


class TestSupervisorMetrics:
    """Tests for supervisor metrics."""
    
    def test_initial_metrics(self):
        """Test initial metric values."""
        supervisor = AgentSupervisor(name="test")
        
        assert supervisor.metrics['tasks_delegated'] == 0
        assert supervisor.metrics['tasks_completed'] == 0
        assert supervisor.metrics['tasks_failed'] == 0
        assert supervisor.metrics['restarts'] == 0
        assert supervisor.metrics['escalations'] == 0
        assert supervisor.metrics['handoffs'] == 0
    
    def test_task_delegated_metric_increments(self):
        """Test that tasks_delegated increments."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker")
        supervisor.add_agent(agent)
        
        def task():
            pass
        
        supervisor.delegate_task(task)
        supervisor.delegate_task(task)
        
        assert supervisor.metrics['tasks_delegated'] == 2


class TestHierarchicalSupervision:
    """Tests for hierarchical supervision trees."""
    
    def test_nested_supervisors(self):
        """Test nested supervisor hierarchy."""
        root = AgentSupervisor(name="root")
        level1 = AgentSupervisor(name="level1")
        level2 = AgentSupervisor(name="level2")
        
        root.add_child_supervisor(level1)
        level1.add_child_supervisor(level2)
        
        assert level1.id in root.child_supervisors
        assert level2.id in level1.child_supervisors
        assert level1.parent_supervisor == root
        assert level2.parent_supervisor == level1
    
    def test_recursive_agent_count(self):
        """Test counting agents recursively through hierarchy."""
        root = AgentSupervisor(name="root")
        child1 = AgentSupervisor(name="child1")
        child2 = AgentSupervisor(name="child2")
        
        root.add_child_supervisor(child1)
        root.add_child_supervisor(child2)
        
        root.add_agent(MockAgent(name="root_agent"))
        child1.add_agent(MockAgent(name="child1_agent1"))
        child1.add_agent(MockAgent(name="child1_agent2"))
        child2.add_agent(MockAgent(name="child2_agent"))
        
        all_agents = root.get_all_agents(recursive=True)
        
        assert len(all_agents) == 4


class TestAgentStates:
    """Tests for agent state management."""
    
    def test_default_agent_state(self):
        """Test default agent state is IDLE."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker")
        
        supervisor.add_agent(agent)
        
        assert supervisor.agent_states[agent.id] == AgentState.IDLE
    
    def test_agent_state_idle(self):
        """Test IDLE state."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker")
        
        supervisor.add_agent(agent)
        supervisor.agent_states[agent.id] = AgentState.IDLE
        
        available = supervisor.get_available_agents()
        assert len(available) == 1
    
    def test_agent_state_busy(self):
        """Test BUSY state excludes from available."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker")
        
        supervisor.add_agent(agent)
        supervisor.agent_states[agent.id] = AgentState.BUSY
        
        available = supervisor.get_available_agents()
        assert len(available) == 0
    
    def test_agent_state_failed(self):
        """Test FAILED state."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker")
        
        supervisor.add_agent(agent)
        supervisor.agent_states[agent.id] = AgentState.FAILED
        
        assert supervisor.agent_states[agent.id] == AgentState.FAILED


class TestSupervisionConfig:
    """Tests for SupervisionConfig."""
    
    def test_default_config(self):
        """Test default config values."""
        config = SupervisionConfig()
        
        # Check defaults exist
        assert config.strategy is not None
        assert config.max_restarts > 0
    
    def test_custom_config(self):
        """Test custom config values."""
        config = SupervisionConfig(
            strategy=SupervisionStrategy.ONE_FOR_ALL,
            max_restarts=10,
            restart_window=300
        )
        
        assert config.strategy == SupervisionStrategy.ONE_FOR_ALL
        assert config.max_restarts == 10
        assert config.restart_window == 300


class TestRestartTracking:
    """Tests for restart tracking."""
    
    def test_initial_restart_counts(self):
        """Test initial restart counts are zero."""
        supervisor = AgentSupervisor(name="test")
        agent = MockAgent(name="worker")
        
        supervisor.add_agent(agent)
        
        assert supervisor.restart_counts[agent.id] == 0
    
    def test_restart_times_tracking(self):
        """Test restart times are tracked."""
        supervisor = AgentSupervisor(name="test")
        
        # Manually track restart
        supervisor.restart_times["agent-1"].append(time.time())
        supervisor.restart_times["agent-1"].append(time.time())
        
        assert len(supervisor.restart_times["agent-1"]) == 2
