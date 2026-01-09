"""
Base Evaluation System.

Provides the fundamental EvaluationSystem class for defining and running
evaluation criteria on data.
"""

from typing import Dict, Any, List, Callable
import logging
import time

from .exceptions import CriterionEvaluationError  # noqa: F401 - exported for library users

logger = logging.getLogger(__name__)


class EvaluationSystem:
    """
    Core evaluation system for defining and running evaluation criteria.
    
    Features:
    - Define custom evaluation criteria
    - Evaluate data against criteria
    - Track evaluation history
    """
    
    def __init__(self):
        self.criteria: Dict[str, Callable[[Any], bool]] = {}
        self.results: List[Dict[str, Any]] = []

    def define_criterion(self, name: str, evaluation_fn: Callable[[Any], bool]):
        """Define an evaluation criterion."""
        self.criteria[name] = evaluation_fn
        self._log(f"Defined evaluation criterion '{name}'")

    def evaluate(self, data: Any) -> Dict[str, bool]:
        """Evaluate data against all defined criteria."""
        evaluation_result = {}
        for name, fn in self.criteria.items():
            try:
                evaluation_result[name] = fn(data)
            except (TypeError, ValueError, KeyError, AttributeError) as e:
                evaluation_result[name] = False
                self._log(f"Error evaluating criterion '{name}': {e}")
                logger.warning("Criterion '%s' evaluation failed: %s", name, e)
            except Exception as e:  # noqa: BLE001 - Fail safe for unknown errors
                evaluation_result[name] = False
                self._log(f"Unexpected error evaluating criterion '{name}': {e}")
                logger.exception("Unexpected error in criterion '%s'", name)
        self.results.append({"data": data, "result": evaluation_result, "timestamp": time.time()})
        return evaluation_result

    def get_results(self) -> List[Dict[str, Any]]:
        """Get all evaluation results."""
        return self.results

    def _log(self, message: str):
        """Internal logging."""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [EvaluationSystem] {message}")


__all__ = ['EvaluationSystem']
