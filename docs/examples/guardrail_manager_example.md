from agenticaiframework.guardrails import Guardrail, GuardrailManager

# Example: Using the Guardrail and GuardrailManager
# -------------------------------------------------
# This example demonstrates how to:
# 1. Create guardrails with validation functions
# 2. Register them with GuardrailManager
# 3. Validate inputs using guardrails
#
# Expected Output:
# - Validation results for given inputs

if __name__ == "__main__":
    # Create a guardrail manager
    guardrail_manager = GuardrailManager()

    # Define some guardrails
    def non_empty_string(value):
        return isinstance(value, str) and len(value.strip()) > 0

    def positive_number(value):
        return isinstance(value, (int, float)) and value > 0

    # Create Guardrail objects
    guardrail1 = Guardrail(name="NonEmptyString", validation_fn=non_empty_string)
    guardrail2 = Guardrail(name="PositiveNumber", validation_fn=positive_number)

    # Register guardrails
    guardrail_manager.register_guardrail(guardrail1)
    guardrail_manager.register_guardrail(guardrail2)

    # Validate some inputs
    print("Validate 'Hello':", guardrail_manager.validate("NonEmptyString", "Hello"))
    print("Validate '':", guardrail_manager.validate("NonEmptyString", ""))
    print("Validate 42:", guardrail_manager.validate("PositiveNumber", 42))
    print("Validate -5:", guardrail_manager.validate("PositiveNumber", -5))
