---
title: Hub Example
description: Register and discover services with Hub for centralized service management
tags:
  - examples
  - hub
  - services
---

# 🏛️ Hub Example

!!! success "Central Service Registry"
    The Hub provides service discovery across **400+ modules** and **237 enterprise features**. See [Hub Documentation](../hub.md).

```python
import logging

logger = logging.getLogger(__name__)

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
    logger.info("Service 'SampleService' registered.")

    # Retrieve and use the service
    service = hub.get_service("SampleService")
    if service:
        logger.info("Service Output:", service())
    else:
        logger.info("Service not found.")

```
