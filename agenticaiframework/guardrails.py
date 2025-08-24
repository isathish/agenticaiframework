from typing import Dict, Any, List, Callable
import uuid
import time


class Guardrail:
    def __init__(self, name: str, validation_fn: Callable[[Any], bool], policy: Dict[str, Any] = None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.validation_fn = validation_fn
        self.policy = policy or {}
        self.version = "1.0.0"

    def validate(self, data: Any) -> bool:
        return self.validation_fn(data)


class GuardrailManager:
    def __init__(self):
        self.guardrails: Dict[str, Guardrail] = {}

    def register_guardrail(self, guardrail: Guardrail):
        self.guardrails[guardrail.id] = guardrail
        self._log(f"Registered guardrail '{guardrail.name}' with ID {guardrail.id}")

    def get_guardrail(self, guardrail_id: str) -> Guardrail:
        return self.guardrails.get(guardrail_id)

    def list_guardrails(self) -> List[Guardrail]:
        return list(self.guardrails.values())

    def remove_guardrail(self, guardrail_id: str):
        if guardrail_id in self.guardrails:
            del self.guardrails[guardrail_id]
            self._log(f"Removed guardrail with ID {guardrail_id}")

    def enforce_guardrails(self, data: Any) -> bool:
        for guardrail in self.guardrails.values():
            if not guardrail.validate(data):
                self._log(f"Guardrail '{guardrail.name}' failed validation.")
                return False
        return True

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [GuardrailManager] {message}")
