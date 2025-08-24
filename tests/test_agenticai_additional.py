import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agenticai.communication import CommunicationManager
from agenticai.configurations import ConfigurationManager
from agenticai.evaluation import EvaluationSystem
from agenticai.guardrails import Guardrail, GuardrailManager
from agenticai.hub import Hub
from agenticai.knowledge import KnowledgeRetriever
from agenticai.llms import LLMManager

def test_register_and_list_protocols(capsys):
    cm = CommunicationManager()
    handler = lambda data: f"Processed {data}"
    cm.register_protocol("test", handler)
    assert "test" in cm.list_protocols()
    captured = capsys.readouterr()
    assert "Registered communication protocol 'test'" in captured.out

def test_send_existing_protocol():
    cm = CommunicationManager()
    cm.register_protocol("echo", lambda data: data)
    result = cm.send("echo", "hello")
    assert result == "hello"

def test_send_nonexistent_protocol(capsys):
    cm = CommunicationManager()
    result = cm.send("missing", "data")
    assert result is None
    captured = capsys.readouterr()
    assert "Protocol 'missing' not found" in captured.out

def test_send_protocol_with_exception(capsys):
    cm = CommunicationManager()
    def faulty_handler(data):
        raise ValueError("fail")
    cm.register_protocol("faulty", faulty_handler)
    result = cm.send("faulty", "data")
    assert result is None
    captured = capsys.readouterr()
    assert "Error sending data via 'faulty'" in captured.out


def test_configuration_manager_set_get_update_remove(capsys):
    cmgr = ConfigurationManager()
    cmgr.set_config("comp1", {"a": 1})
    assert cmgr.get_config("comp1") == {"a": 1}
    cmgr.update_config("comp1", {"b": 2})
    assert cmgr.get_config("comp1") == {"a": 1, "b": 2}
    cmgr.update_config("comp2", {"x": 9})
    assert cmgr.get_config("comp2") == {"x": 9}
    cmgr.remove_config("comp1")
    assert "comp1" not in cmgr.list_components()
    captured = capsys.readouterr()
    assert "Configuration set for 'comp1'" in captured.out
    assert "Configuration updated for 'comp1'" in captured.out
    assert "Configuration set for 'comp2'" in captured.out
    assert "Configuration removed for 'comp1'" in captured.out


def test_evaluation_system_define_and_evaluate(capsys):
    es = EvaluationSystem()
    es.define_criterion("is_positive", lambda x: x > 0)
    es.define_criterion("is_even", lambda x: x % 2 == 0)
    result = es.evaluate(4)
    assert result == {"is_positive": True, "is_even": True}
    results_list = es.get_results()
    assert len(results_list) == 1
    assert results_list[0]["result"] == result
    captured = capsys.readouterr()
    assert "Defined evaluation criterion 'is_positive'" in captured.out
    assert "Defined evaluation criterion 'is_even'" in captured.out

def test_evaluation_system_with_exception(capsys):
    es = EvaluationSystem()
    def faulty(x):
        raise ValueError("fail")
    es.define_criterion("faulty", faulty)
    result = es.evaluate(10)
    assert result == {"faulty": False}
    captured = capsys.readouterr()
    assert "Error evaluating criterion 'faulty'" in captured.out


def test_guardrail_and_manager(capsys):
    g = Guardrail(name="positive_check", validation_fn=lambda x: x > 0)
    assert g.validate(5) is True
    assert g.validate(-1) is False

    gm = GuardrailManager()
    gm.register_guardrail(g)
    assert gm.get_guardrail(g.id) == g
    assert g in gm.list_guardrails()
    assert gm.enforce_guardrails(10) is True
    assert gm.enforce_guardrails(-5) is False
    gm.remove_guardrail(g.id)
    assert gm.get_guardrail(g.id) is None
    captured = capsys.readouterr()
    assert "Registered guardrail" in captured.out
    assert "Guardrail 'positive_check' failed validation." in captured.out
    assert "Removed guardrail" in captured.out


def test_hub_register_get_list_remove(capsys):
    hub = Hub()
    hub.register("agents", "agent1", {"id": 1})
    assert hub.get("agents", "agent1") == {"id": 1}
    assert "agent1" in hub.list_items("agents")
    hub.remove("agents", "agent1")
    assert "agent1" not in hub.list_items("agents")
    hub.register("invalid", "x", {})
    captured = capsys.readouterr()
    assert "Registered agent 'agent1'" in captured.out
    assert "Removed agent 'agent1'" in captured.out
    assert "Invalid category 'invalid'" in captured.out


def test_knowledge_retriever_register_retrieve_cache_clear(capsys):
    kr = KnowledgeRetriever()
    kr.register_source("source1", lambda q: [{"q": q, "a": "answer"}])
    results = kr.retrieve("test")
    assert results == [{"q": "test", "a": "answer"}]
    # Test cache hit
    results_cached = kr.retrieve("test")
    assert results_cached == results
    kr.clear_cache()
    assert kr.cache == {}
    captured = capsys.readouterr()
    assert "Registered knowledge source 'source1'" in captured.out
    assert "Retrieved 1 items from source 'source1'" in captured.out
    assert "Cache hit for query 'test'" in captured.out
    assert "Knowledge cache cleared" in captured.out

def test_knowledge_retriever_with_exception(capsys):
    kr = KnowledgeRetriever()
    kr.register_source("bad_source", lambda q: (_ for _ in ()).throw(ValueError("fail")))
    results = kr.retrieve("query")
    assert results == []
    captured = capsys.readouterr()
    assert "Error retrieving from source 'bad_source'" in captured.out


def test_llm_manager_register_set_generate_list(capsys):
    lm = LLMManager()
    lm.register_model("m1", lambda prompt, kwargs: f"Response to {prompt}")
    assert "m1" in lm.list_models()
    lm.set_active_model("m1")
    result = lm.generate("Hello")
    assert "Response to Hello" in result
    captured = capsys.readouterr()
    assert "Registered LLM model 'm1'" in captured.out
    assert "Active LLM model set to 'm1'" in captured.out

def test_llm_manager_no_active_model(capsys):
    lm = LLMManager()
    result = lm.generate("test")
    assert result is None
    captured = capsys.readouterr()
    assert "No active model set" in captured.out

def test_llm_manager_with_exception(capsys):
    lm = LLMManager()
    def faulty(prompt, kwargs):
        raise ValueError("fail")
    lm.register_model("bad", faulty)
    lm.set_active_model("bad")
    result = lm.generate("test")
    assert result is None
    captured = capsys.readouterr()
    assert "Error generating with model 'bad'" in captured.out
