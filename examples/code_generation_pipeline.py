from agenticaiframework.agents import Agent
from agenticaiframework.tasks import Task
from agenticaiframework.llms import LLMManager
from agenticaiframework.guardrails import Guardrail
from agenticaiframework.monitoring import Monitor
from agenticaiframework.evaluation import Evaluator

# Example: Code Generation and Evaluation Pipeline
if __name__ == "__main__":
    # Initialize components
    llm = LLMManager()
    llm.register_model("gpt-4", lambda prompt, kwargs: f"[Simulated GPT-4 Code Generation for: {prompt}]")
    llm.set_active_model("gpt-4")
    guardrail = Guardrail(rules=["Generate syntactically correct code", "Avoid insecure code patterns"])
    monitor = Monitor()
    evaluator = Evaluator(metrics=["correctness", "efficiency", "readability"])

    # Create agent
    code_agent = Agent(
        name="CodeGenAgent",
        role="Code Generator",
        capabilities=["generate_code", "evaluate_code"],
        config={"llm": llm, "guardrail": guardrail, "monitor": monitor}
    )

    # Define task
    code_task = Task(
        name="FibonacciCodeGen",
        objective="Generate a Python function that calculates the nth Fibonacci number using memoization.",
        executor=lambda: llm.generate("Write a Python function for nth Fibonacci number using memoization.")
    )

    # Run task
    generated_code = code_task.run()

    # Evaluate code
    evaluation_result = evaluator.evaluate(generated_code)

    # Output results
    print("=== Generated Code ===")
    print(generated_code)
    print("\n=== Evaluation Result ===")
    print(evaluation_result)
