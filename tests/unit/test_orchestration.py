"""
Comprehensive tests for orchestration module.

Tests for:
- AgentTeam
- OrchestrationEngine
- AgentHandoff (dataclass)
- AgentSupervisor
"""

import pytest
from datetime import datetime
from unittest.mock import Mock


class TestAgentTeam:
    """Tests for AgentTeam."""
    
    def test_init(self):
        """Test team initialization."""
        from agenticaiframework.orchestration.teams import AgentTeam
        
        team = AgentTeam(name="test_team", goal="Test the system")
        assert team.name == "test_team"
        assert team.goal == "Test the system"
        assert team.id is not None
    
    def test_init_with_roles(self):
        """Test team initialization with roles."""
        from agenticaiframework.orchestration.teams import AgentTeam
        from agenticaiframework.orchestration.models import TeamRole
        
        roles = [
            TeamRole(name="leader", description="Team lead"),
            TeamRole(name="worker", description="Worker agent", max_agents=3)
        ]
        
        team = AgentTeam(name="test_team", goal="Complete tasks", roles=roles)
        assert len(team.roles) == 2
    
    def test_add_role(self):
        """Test adding role to team."""
        from agenticaiframework.orchestration.teams import AgentTeam
        from agenticaiframework.orchestration.models import TeamRole
        
        team = AgentTeam(name="test_team", goal="Test")
        role = TeamRole(name="analyst", description="Data analyst")
        
        team.add_role(role)
        assert len(team.roles) == 1
    
    def test_add_member(self):
        """Test adding member to team."""
        from agenticaiframework.orchestration.teams import AgentTeam
        from agenticaiframework.orchestration.models import TeamRole
        
        team = AgentTeam(name="test_team", goal="Test")
        role = TeamRole(name="worker", description="Worker")
        team.add_role(role)
        
        mock_agent = Mock()
        mock_agent.id = "agent1"
        mock_agent.add_context = Mock()
        
        team.add_member(mock_agent, "worker")
        assert "agent1" in team.members
    
    def test_remove_member(self):
        """Test removing member from team."""
        from agenticaiframework.orchestration.teams import AgentTeam
        from agenticaiframework.orchestration.models import TeamRole
        
        team = AgentTeam(name="test_team", goal="Test")
        role = TeamRole(name="worker", description="Worker")
        team.add_role(role)
        
        mock_agent = Mock()
        mock_agent.id = "agent1"
        mock_agent.add_context = Mock()
        
        team.add_member(mock_agent, "worker")
        team.remove_member("agent1")
        
        assert "agent1" not in team.members
    
    def test_get_members_by_role(self):
        """Test getting members by role."""
        from agenticaiframework.orchestration.teams import AgentTeam
        from agenticaiframework.orchestration.models import TeamRole
        
        team = AgentTeam(name="test_team", goal="Test")
        role = TeamRole(name="worker", description="Worker", max_agents=5)
        team.add_role(role)
        
        mock_agent = Mock()
        mock_agent.id = "agent1"
        mock_agent.add_context = Mock()
        
        team.add_member(mock_agent, "worker")
        
        workers = team.get_members_by_role("worker")
        assert len(workers) == 1


class TestOrchestrationEngine:
    """Tests for OrchestrationEngine."""
    
    def test_init(self):
        """Test engine initialization."""
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        
        engine = OrchestrationEngine()
        assert engine.teams == {}
        assert engine.supervisors == {}
    
    def test_register_team(self):
        """Test registering team."""
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        from agenticaiframework.orchestration.teams import AgentTeam
        
        engine = OrchestrationEngine()
        team = AgentTeam(name="test_team", goal="Test")
        
        engine.register_team(team)
        assert team.id in engine.teams
    
    def test_register_supervisor(self):
        """Test registering supervisor."""
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        from agenticaiframework.orchestration.supervisor import AgentSupervisor
        
        engine = OrchestrationEngine()
        supervisor = AgentSupervisor(name="test_supervisor")
        
        engine.register_supervisor(supervisor)
        assert supervisor.id in engine.supervisors
    
    def test_sequential_orchestration(self):
        """Test sequential orchestration pattern."""
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        from agenticaiframework.orchestration.types import OrchestrationPattern
        
        engine = OrchestrationEngine()
        
        mock_agent1 = Mock()
        mock_agent1.execute_task = Mock(return_value="result1")
        mock_agent2 = Mock()
        mock_agent2.execute_task = Mock(return_value="result2")
        
        def task():
            return "task_output"
        
        results = engine.orchestrate(
            agents=[mock_agent1, mock_agent2],
            task_callable=task,
            pattern=OrchestrationPattern.SEQUENTIAL
        )
        
        assert len(results) == 2
    
    def test_parallel_orchestration(self):
        """Test parallel orchestration pattern."""
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        from agenticaiframework.orchestration.types import OrchestrationPattern
        
        engine = OrchestrationEngine()
        
        mock_agent1 = Mock()
        mock_agent1.execute_task = Mock(return_value="result1")
        mock_agent2 = Mock()
        mock_agent2.execute_task = Mock(return_value="result2")
        
        def task():
            return "task_output"
        
        results = engine.orchestrate(
            agents=[mock_agent1, mock_agent2],
            task_callable=task,
            pattern=OrchestrationPattern.PARALLEL
        )
        
        assert len(results) == 2
    
    def test_orchestration_with_aggregator(self):
        """Test orchestration with result aggregator."""
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        from agenticaiframework.orchestration.types import OrchestrationPattern
        
        engine = OrchestrationEngine()
        
        mock_agent1 = Mock()
        mock_agent1.execute_task = Mock(return_value=10)
        mock_agent2 = Mock()
        mock_agent2.execute_task = Mock(return_value=20)
        
        def task():
            return 0
        
        result = engine.orchestrate(
            agents=[mock_agent1, mock_agent2],
            task_callable=task,
            pattern=OrchestrationPattern.SEQUENTIAL,
            aggregator=sum
        )
        
        assert result == 30


class TestAgentHandoffModel:
    """Tests for AgentHandoff dataclass."""
    
    def test_create_handoff(self):
        """Test creating handoff record."""
        from agenticaiframework.orchestration.models import AgentHandoff
        
        handoff = AgentHandoff(
            handoff_id="h1",
            from_agent_id="agent1",
            to_agent_id="agent2",
            context={"task": "process_data"},
            reason="capability_match"
        )
        
        assert handoff.from_agent_id == "agent1"
        assert handoff.to_agent_id == "agent2"
        assert handoff.success is True
    
    def test_handoff_to_dict(self):
        """Test handoff to_dict method."""
        from agenticaiframework.orchestration.models import AgentHandoff
        
        handoff = AgentHandoff(
            handoff_id="h1",
            from_agent_id="agent1",
            to_agent_id="agent2",
            context={"data": "value"},
            reason="test"
        )
        
        d = handoff.to_dict()
        assert d['handoff_id'] == "h1"
        assert d['from_agent_id'] == "agent1"


class TestTaskAssignment:
    """Tests for TaskAssignment dataclass."""
    
    def test_create_assignment(self):
        """Test creating task assignment."""
        from agenticaiframework.orchestration.models import TaskAssignment
        
        assignment = TaskAssignment(
            task_id="task1",
            agent_id="agent1",
            task_callable=None
        )
        
        assert assignment.task_id == "task1"
        assert assignment.status == "pending"
    
    def test_assignment_can_retry(self):
        """Test can_retry property."""
        from agenticaiframework.orchestration.models import TaskAssignment
        
        assignment = TaskAssignment(
            task_id="task1",
            agent_id="agent1",
            task_callable=None,
            retries=0,
            max_retries=3
        )
        
        assert assignment.can_retry is True
        
        assignment.retries = 3
        assert assignment.can_retry is False
    
    def test_assignment_is_complete(self):
        """Test is_complete property."""
        from agenticaiframework.orchestration.models import TaskAssignment
        
        assignment = TaskAssignment(
            task_id="task1",
            agent_id="agent1",
            task_callable=None,
            status="pending"
        )
        
        assert assignment.is_complete is False
        
        assignment.status = "completed"
        assert assignment.is_complete is True


class TestTeamRole:
    """Tests for TeamRole dataclass."""
    
    def test_create_role(self):
        """Test creating team role."""
        from agenticaiframework.orchestration.models import TeamRole
        
        role = TeamRole(
            name="analyst",
            description="Data analyst role",
            required_capabilities=["data_processing"]
        )
        
        assert role.name == "analyst"
        assert role.max_agents == 1
    
    def test_role_is_valid_count(self):
        """Test is_valid_count method."""
        from agenticaiframework.orchestration.models import TeamRole
        
        role = TeamRole(
            name="worker",
            description="Worker",
            min_agents=1,
            max_agents=5
        )
        
        assert role.is_valid_count(3) is True
        assert role.is_valid_count(0) is False
        assert role.is_valid_count(10) is False


class TestSupervisionConfig:
    """Tests for SupervisionConfig dataclass."""
    
    def test_create_config(self):
        """Test creating supervision config."""
        from agenticaiframework.orchestration.models import SupervisionConfig
        from agenticaiframework.orchestration.types import SupervisionStrategy
        
        config = SupervisionConfig(
            strategy=SupervisionStrategy.ONE_FOR_ONE,
            max_restarts=5
        )
        
        assert config.max_restarts == 5
    
    def test_config_get_backoff(self):
        """Test backoff calculation."""
        from agenticaiframework.orchestration.models import SupervisionConfig
        
        config = SupervisionConfig(
            initial_backoff=1.0,
            backoff_multiplier=2.0,
            max_backoff=60.0
        )
        
        assert config.get_backoff(0) == 1.0
        assert config.get_backoff(1) == 2.0
        assert config.get_backoff(2) == 4.0
        assert config.get_backoff(10) == 60.0  # Capped at max


class TestOrchestrationTypes:
    """Tests for orchestration types."""
    
    def test_orchestration_pattern_enum(self):
        """Test orchestration pattern enum."""
        from agenticaiframework.orchestration.types import OrchestrationPattern
        
        assert OrchestrationPattern.SEQUENTIAL
        assert OrchestrationPattern.PARALLEL
        assert OrchestrationPattern.HIERARCHICAL
    
    def test_supervision_strategy_enum(self):
        """Test supervision strategy enum."""
        from agenticaiframework.orchestration.types import SupervisionStrategy
        
        assert SupervisionStrategy.ONE_FOR_ONE
        assert SupervisionStrategy.ONE_FOR_ALL
        assert SupervisionStrategy.REST_FOR_ONE
    
    def test_agent_state_enum(self):
        """Test agent state enum."""
        from agenticaiframework.orchestration.types import AgentState
        
        assert AgentState.IDLE
        assert AgentState.BUSY
        assert AgentState.FAILED


class TestOrchestrationIntegration:
    """Integration tests for orchestration."""
    
    def test_team_with_engine(self):
        """Test team with orchestration engine."""
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        from agenticaiframework.orchestration.teams import AgentTeam
        
        engine = OrchestrationEngine()
        team = AgentTeam(name="test_team", goal="Test integration")
        
        engine.register_team(team)
        assert len(engine.teams) == 1
    
    def test_supervisor_with_engine(self):
        """Test supervisor with orchestration engine."""
        from agenticaiframework.orchestration.engine import OrchestrationEngine
        from agenticaiframework.orchestration.supervisor import AgentSupervisor
        
        engine = OrchestrationEngine()
        supervisor = AgentSupervisor(name="test_supervisor")
        
        engine.register_supervisor(supervisor)
        assert len(engine.supervisors) == 1
