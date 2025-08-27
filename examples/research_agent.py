from agenticaiframework.agents import Agent
from agenticaiframework.tasks import Task
from agenticaiframework.llms import LLMManager
from agenticaiframework.guardrails import Guardrail
from agenticaiframework.monitoring import Monitor

# Example: AI Agent solving a research question
if __name__ == "__main__":
    # Initialize components
    llm = LLMManager()
    llm.register_model("gpt-4", lambda prompt, kwargs: f"[Simulated GPT-4 Response to: {prompt}]")
    llm.set_active_model("gpt-4")
    guardrail = Guardrail(rules=["No harmful content", "Cite sources"])
    monitor = Monitor()

    # Create agent
    research_agent = Agent(
        name="ResearchAgent",
        llm=llm,
        guardrail=guardrail,
        monitor=monitor
    )

    # Define task
    research_task = Task(
        description="Research the impact of climate change on polar bear populations and summarize findings with citations.",
        expected_output="A concise, factual summary with at least 2 citations."
    )

    # Run task
    result = research_agent.run_task(research_task)

    # Output result
    print("=== Research Result ===")
    print(result)
