from typing import Dict, Any, Callable, Optional
import time


class LLMManager:
    def __init__(self):
        self.models: Dict[str, Callable[[str, Dict[str, Any]], str]] = {}
        self.active_model: Optional[str] = None

    def register_model(self, name: str, inference_fn: Callable[[str, Dict[str, Any]], str]):
        self.models[name] = inference_fn
        self._log(f"Registered LLM model '{name}'")

    def set_active_model(self, name: str):
        if name in self.models:
            self.active_model = name
            self._log(f"Active LLM model set to '{name}'")
        else:
            self._log(f"Model '{name}' not found")

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        if not self.active_model:
            self._log("No active model set")
            return None
        try:
            return self.models[self.active_model](prompt, kwargs)
        except Exception as e:
            self._log(f"Error generating with model '{self.active_model}': {e}")
            return None

    def list_models(self):
        return list(self.models.keys())

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [LLMManager] {message}")
