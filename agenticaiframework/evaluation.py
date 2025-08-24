from typing import Dict, Any, List, Callable
import time


class EvaluationSystem:
    def __init__(self):
        self.criteria: Dict[str, Callable[[Any], bool]] = {}
        self.results: List[Dict[str, Any]] = []

    def define_criterion(self, name: str, evaluation_fn: Callable[[Any], bool]):
        self.criteria[name] = evaluation_fn
        self._log(f"Defined evaluation criterion '{name}'")

    def evaluate(self, data: Any) -> Dict[str, bool]:
        evaluation_result = {}
        for name, fn in self.criteria.items():
            try:
                evaluation_result[name] = fn(data)
            except Exception as e:
                evaluation_result[name] = False
                self._log(f"Error evaluating criterion '{name}': {e}")
        self.results.append({"data": data, "result": evaluation_result, "timestamp": time.time()})
        return evaluation_result

    def get_results(self) -> List[Dict[str, Any]]:
        return self.results

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [EvaluationSystem] {message}")
