from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any, Callable, Dict, List

from .exceptions import CriterionEvaluationError  # noqa: F401 - exported for library users

logger = logging.getLogger(__name__)

_MAX_RESULTS = 5_000


class EvaluationSystem:
    """Core evaluation system with bounded result history."""

    def __init__(self, max_results: int = _MAX_RESULTS) -> None:
        self.criteria: Dict[str, Callable[[Any], bool]] = {}
        self.results: deque[Dict[str, Any]] = deque(maxlen=max_results)

    def define_criterion(self, name: str, evaluation_fn: Callable[[Any], bool]) -> None:
        self.criteria[name] = evaluation_fn
        logger.info("Defined evaluation criterion '%s'", name)

    def evaluate(self, data: Any) -> Dict[str, bool]:
        evaluation_result: Dict[str, bool] = {}
        for name, fn in self.criteria.items():
            try:
                evaluation_result[name] = fn(data)
            except (TypeError, ValueError, KeyError, AttributeError) as e:
                evaluation_result[name] = False
                logger.warning("Criterion '%s' evaluation failed: %s", name, e)
            except Exception as e:  # noqa: BLE001 - Fail safe for unknown errors
                evaluation_result[name] = False
                logger.exception("Unexpected error in criterion '%s'", name)
        self.results.append({"data": data, "result": evaluation_result, "timestamp": time.time()})
        return evaluation_result

    def get_results(self) -> List[Dict[str, Any]]:
        return list(self.results)
