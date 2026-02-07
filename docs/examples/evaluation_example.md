---
title: Evaluation Example
description: Create evaluation criteria and assess AI outputs with EvaluationSystem
tags:
  - examples
  - evaluation
  - assessment
---

# 📊 Evaluation System Example

!!! tip "12-Tier Evaluation System"
    Part of **400+ modules** with a comprehensive **12-tier evaluation system** and 100+ metrics. See [Evaluation Documentation](../evaluation.md).

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.evaluation import EvaluationSystem

# Example: Using the EvaluationSystem
# ------------------------------------
# This example demonstrates how to:
# 1. Create an EvaluationSystem
# 2. Add evaluation criteria
# 3. Evaluate a sample output
#
# Expected Output:
# - Evaluation results printed to the console

if __name__ == "__main__":
    # Create an evaluation system
    evaluator = EvaluationSystem()

    # Define a simple evaluation criterion
    def length_check(output):
        return len(output) > 5

    # Add the criterion to the evaluator
    evaluator.add_criterion("Length Check", length_check)

    # Evaluate a sample output
    sample_output = "Hello World"
    results = evaluator.evaluate(sample_output)

    logger.info("Evaluation Results:", results)

```
