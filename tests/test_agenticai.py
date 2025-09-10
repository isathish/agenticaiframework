import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agenticaiframework.agents import Agent, AgentManager
from agenticaiframework.prompts import Prompt, PromptManager
from agenticaiframework.processes import Process
from agenticaiframework.tasks import Task, TaskManager

def sample_task(x, y):
    return x + y

def test_agent_lifecycle_and_task_execution(capsys):
    agent = Agent(name="TestAgent", role="tester", capabilities=["compute"], config={})
    agent.start()
    agent.pause()
    agent.resume()
    agent.stop()
    result = agent.execute_task(sample_task, 2, 3)
    assert result == 5
    captured = capsys.readouterr()
    assert "started" in captured.out
    assert "paused" in captured.out
    assert "resumed" in captured.out
    assert "stopped" in captured.out

def test_agent_manager_register_and_broadcast(capsys):
    manager = AgentManager()
    agent = Agent(name="A1", role="r1", capabilities=[], config={})
    manager.register_agent(agent)
    assert manager.get_agent(agent.id) == agent
    assert agent in manager.list_agents()
    manager.broadcast("Hello")
    manager.remove_agent(agent.id)
    assert manager.get_agent(agent.id) is None
    captured = capsys.readouterr()
    assert "Registered agent" in captured.out
    assert "Broadcast message" in captured.out
    assert "Removed agent" in captured.out

def test_prompt_render_and_optimization(capsys):
    prompt = Prompt(template="Hello {name}")
    assert prompt.render(name="World") == "Hello World"
    pm = PromptManager()
    pm.register_prompt(prompt)
    assert pm.get_prompt(prompt.id) == prompt
    assert prompt in pm.list_prompts()
    pm.optimize_prompt(prompt.id, lambda t: t.upper())
    assert prompt.template == "HELLO {NAME}"
    pm.remove_prompt(prompt.id)
    assert pm.get_prompt(prompt.id) is None
    captured = capsys.readouterr()
    assert "Registered prompt" in captured.out
    assert "Optimized prompt" in captured.out
    assert "Removed prompt" in captured.out

def test_process_execution_strategies():
    p_seq = Process(name="seq", strategy="sequential")
    p_seq.add_task(sample_task, 1, 2)
    assert p_seq.execute() == [3]

    p_par = Process(name="par", strategy="parallel")
    p_par.add_task(sample_task, 2, 3)
    p_par.add_task(sample_task, 4, 5)
    results = p_par.execute()
    assert sorted(results) == [5, 9]

    p_hybrid = Process(name="hyb", strategy="hybrid")
    p_hybrid.add_task(sample_task, 1, 1)
    p_hybrid.add_task(sample_task, 2, 2)
    p_hybrid.add_task(sample_task, 3, 3)
    results = p_hybrid.execute()
    assert sorted(results) == [2, 4, 6]

def test_task_run_and_manager(capsys):
    t = Task(name="T1", objective="sum", executor=sample_task, inputs={"x": 5, "y": 7})
    result = t.run()
    assert result == 12
    tm = TaskManager()
    tm.register_task(t)
    assert tm.get_task(t.id) == t
    assert t in tm.list_tasks()
    tm.remove_task(t.id)
    assert tm.get_task(t.id) is None
    captured = capsys.readouterr()
    assert "Registered task" in captured.out
    assert "Removed task" in captured.out

def test_task_manager_run_all():
    tm = TaskManager()
    t1 = Task(name="T1", objective="sum", executor=sample_task, inputs={"x": 1, "y": 2})
    t2 = Task(name="T2", objective="sum", executor=sample_task, inputs={"x": 3, "y": 4})
    tm.register_task(t1)
    tm.register_task(t2)
    results = tm.run_all()
    assert results[t1.id] == 3
    assert results[t2.id] == 7
