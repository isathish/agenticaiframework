from agenticaiframework.agents import Agent
from agenticaiframework.tasks import Task
from agenticaiframework.llms import LLMManager
from agenticaiframework.guardrails import Guardrail
from agenticaiframework.monitoring import Monitor

# Example: Automated Customer Support Bot
if __name__ == "__main__":
    # Initialize components
    llm = LLMManager()
    llm.register_model("gpt-4", lambda prompt, kwargs: f"[Simulated GPT-4 Support Response to: {prompt}]")
    llm.set_active_model("gpt-4")
    guardrail = Guardrail(rules=["Be polite", "Do not provide personal data", "Stay on topic"])
    monitor = Monitor()

    # Create agent
    support_agent = Agent(
        name="CustomerSupportBot",
        llm=llm,
        guardrail=guardrail,
        monitor=monitor
    )

    # Define task
    support_task = Task(
        description="Respond to a customer asking about the refund policy for defective products.",
        expected_output="A polite, clear explanation of the refund policy."
    )

    # Run task
    result = support_agent.run_task(support_task)

    # Output result
    print("=== Customer Support Response ===")
    print(result)
