from agenticaiframework.guardrails import Guardrail

# Example: Using Guardrail to validate outputs
# --------------------------------------------
# This example demonstrates how to:
# 1. Create a Guardrail with validation rules
# 2. Validate outputs against the rules
#
# Expected Output:
# - Validation results for compliant and non-compliant outputs

if __name__ == "__main__":
    # Define a simple validation function
    def validate_output(output: str) -> bool:
        # Example rule: output must not contain banned words
        banned_words = ["error", "fail"]
        return not any(word in output.lower() for word in banned_words)

    # Create a Guardrail instance
    guardrail = Guardrail(
        name="NoBannedWords",
        validation_fn=validate_output
    )

    # Test compliant output
    compliant_output = "This is a safe and valid response."
    is_valid = guardrail.validate(compliant_output)
    print(f"Compliant Output Valid: {is_valid}")

    # Test non-compliant output
    non_compliant_output = "This response contains an error."
    is_valid = guardrail.validate(non_compliant_output)
    print(f"Non-Compliant Output Valid: {is_valid}")
