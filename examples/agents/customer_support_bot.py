from agenticaiframework.agents import Agent
from agenticaiframework.tasks import Task
from agenticaiframework.llms import LLMManager
from agenticaiframework.guardrails import Guardrail
from agenticaiframework.monitoring import MonitoringSystem

# Example: Automated Customer Support Bot
if __name__ == "__main__":
    # Initialize components
    llm = LLMManager()
    llm.register_model("gpt-4", lambda prompt, kwargs: f"[Simulated GPT-4 Support Response to: {prompt}]")
    llm.set_active_model("gpt-4")
    guardrail = Guardrail(name="SupportGuardrail", validation_fn=lambda text: len(text) > 0)
    monitor = MonitoringSystem()

    # Create agent
    support_agent = Agent(
        name="CustomerSupportBot",
        role="Customer Support Assistant",
        capabilities=["answer_questions", "provide_support", "escalate_issues"],
        config={
            "llm": llm,
            "guardrail": guardrail,
            "monitor": monitor
        }
    )

    # Define task
    support_task = Task(
        name="CustomerSupportTask",
        objective="Respond to a customer asking about the refund policy for defective products.",
        executor=lambda: llm.generate("Please explain our refund policy for defective products in a polite and clear manner.")
    )

    # Run task
    result = support_task.run()

    # Output result
    print("=== Customer Support Response ===")
    print(result)
