---
tags:
  - examples
  - hub
  - services
---

# Hub Example

```python
from agenticaiframework.hub import Hub

# Example: Using the Hub
# ----------------------
# This example demonstrates how to:
# 1. Create a Hub
# 2. Register services
# 3. Retrieve and use services
#
# Expected Output:
# - Confirmation of service registration
# - Output from the retrieved service

if __name__ == "__main__":
    # Create a hub
    hub = Hub()

    # Define a sample service
    def sample_service():
        return "Service executed successfully."

    # Register the service
    hub.register_service("SampleService", sample_service)
    print("Service 'SampleService' registered.")

    # Retrieve and use the service
    service = hub.get_service("SampleService")
    if service:
        print("Service Output:", service())
    else:
        print("Service not found.")

```
