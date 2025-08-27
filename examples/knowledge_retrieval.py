from agenticaiframework.agents import Agent
from agenticaiframework.tasks import Task
from agenticaiframework.llms import LLMManager
from agenticaiframework.guardrails import Guardrail
from agenticaiframework.monitoring import Monitor
from agenticaiframework.knowledge import KnowledgeRetriever

# Example: Knowledge Retrieval and Summarization
if __name__ == "__main__":
    # Initialize components
    llm = LLMManager()
    llm.register_model("gpt-4", lambda prompt, kwargs: f"[Simulated GPT-4 Knowledge Retrieval for: {prompt}]")
    llm.set_active_model("gpt-4")
    guardrail = Guardrail(rules=["Provide factual information", "Cite sources"])
    monitor = Monitor()
    knowledge_base = KnowledgeRetriever()
    knowledge_base.register_source("local_corpus", lambda query: [
        {"title": "Quantum Computing History", "content": "Quantum computing research began in the 1980s... [Source 1]"},
        {"title": "Quantum Computing Milestones", "content": "Key milestones include Shor's algorithm in 1994... [Source 2]"}
    ])

    # Create agent
    knowledge_agent = Agent(
        name="KnowledgeRetrievalAgent",
        role="Knowledge Specialist",
        capabilities=["retrieve_information", "summarize"],
        config={"llm": llm, "guardrail": guardrail, "monitor": monitor, "knowledge_base": knowledge_base}
    )

    # Define task
    knowledge_task = Task(
        name="QuantumComputingHistory",
        objective="Retrieve and summarize information about the history of quantum computing.",
        executor=lambda: llm.generate("Summarize the history of quantum computing with at least 2 citations.")
    )

    # Run task
    result = knowledge_task.run()

    # Output result
    print("=== Knowledge Retrieval Summary ===")
    print(result)
