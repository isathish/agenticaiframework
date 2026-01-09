from agenticaiframework.agents import Agent
from agenticaiframework.tasks import Task
from agenticaiframework.llms import LLMManager
from agenticaiframework.guardrails import Guardrail
from agenticaiframework.monitoring import MonitoringSystem

# Example: AI Agent solving a research question
if __name__ == "__main__":
        # Initialize components
    llm = LLMManager()
    llm.register_model("gpt-4", lambda prompt, kwargs: f"[Simulated GPT-4 Response to: {prompt}]")
    llm.set_active_model("gpt-4")
    guardrail = Guardrail(name="ResearchGuardrail", validation_fn=lambda text: len(text) > 0 and "harmful" not in text.lower())
    monitor = MonitoringSystem()

    # Create agent
    research_agent = Agent(
        name="ResearchAgent",
        role="Research Assistant",
        capabilities=["research", "summarize", "cite_sources"],
        config={
            "llm": llm,
            "guardrail": guardrail,
            "monitor": monitor
        }
    )

    # Define task
    research_task = Task(
        name="ClimateResearchTask",
        objective="Research the impact of climate change on polar bear populations and summarize findings with citations.",
        executor=lambda: llm.generate("Research and summarize the impact of climate change on polar bear populations with citations.")
    )

    # Run task
    result = research_task.run()

    # Output result
    print("=== Research Result ===")
    print(result)
