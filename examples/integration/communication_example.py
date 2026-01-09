from agenticaiframework.communication import CommunicationManager

# Example: Using the CommunicationManager
# ----------------------------------------
# This example demonstrates how to:
# 1. Create a CommunicationManager
# 2. Send and receive messages
#
# Expected Output:
# - Logs showing messages being sent and received

if __name__ == "__main__":
    # Create a communication manager
    comm_manager = CommunicationManager()

    # Define a simple message handler
    def message_handler(message):
        print(f"Received message: {message}")

    # Register the handler
    comm_manager.register_handler(message_handler)

    # Send a message
    comm_manager.send_message("Hello from CommunicationManager!")
