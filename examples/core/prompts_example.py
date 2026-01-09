from agenticaiframework.prompts import Prompt

# Example: Using Prompt to format prompts
# ---------------------------------------
# This example demonstrates how to:
# 1. Create a Prompt instance
# 2. Format a prompt with variables
#
# Expected Output:
# - Formatted prompt string with variables replaced

if __name__ == "__main__":
    # Create a Prompt instance
    prompt_instance = Prompt(
        template="Write a {length} paragraph summary about {topic}."
    )

    # Render the prompt with actual values
    rendered_prompt = prompt_instance.render(length="short", topic="artificial intelligence")
    print("Rendered Prompt:", rendered_prompt)
