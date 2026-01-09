from agenticaiframework.llms import LLMManager

# Example: Using LLMManager to register and generate text
# -------------------------------------------------------
# This example demonstrates how to:
# 1. Create an LLMManager instance
# 2. Register a simulated LLM model
# 3. Set the active model
# 4. Generate text from a prompt
# 5. List available models
#
# Expected Output:
# - Confirmation of model registration
# - Confirmation of active model setting
# - Generated text from the prompt
# - List of registered models

if __name__ == "__main__":
    # Create LLMManager instance
    llm_manager = LLMManager()

    # Register a simulated model
    llm_manager.register_model("demo-llm", lambda prompt, kwargs: f"[Demo LLM Response to: {prompt}]")

    # Set the active model
    llm_manager.set_active_model("demo-llm")

    # Generate text from a prompt
    prompt_text = "Explain the concept of machine learning in simple terms."
    generated_text = llm_manager.generate(prompt_text)
    print("Generated Text:", generated_text)

    # List available models
    models = llm_manager.list_models()
    print("Available Models:", models)
