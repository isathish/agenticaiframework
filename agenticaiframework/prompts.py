from typing import Any, Dict, List
import uuid
import time


class Prompt:
    def __init__(self, template: str, metadata: Dict[str, Any] = None):
        self.id = str(uuid.uuid4())
        self.template = template
        self.metadata = metadata or {}
        self.version = "1.0.0"

    def render(self, **kwargs) -> str:
        return self.template.format(**kwargs)


class PromptManager:
    def __init__(self):
        self.prompts: Dict[str, Prompt] = {}

    def register_prompt(self, prompt_or_name, prompt_obj=None):
        if isinstance(prompt_or_name, Prompt):
            # Original behavior: register a Prompt object
            prompt = prompt_or_name
            self.prompts[prompt.id] = prompt
            self._log(f"Registered prompt with ID {prompt.id}")
        elif isinstance(prompt_or_name, str) and prompt_obj is not None:
            # New behavior: register with a name and Prompt object
            prompt = prompt_obj
            prompt.metadata = prompt.metadata or {}
            prompt.metadata['name'] = prompt_or_name
            self.prompts[prompt.id] = prompt
            self._log(f"Registered prompt '{prompt_or_name}' with ID {prompt.id}")
        else:
            self._log("Invalid arguments for register_prompt")

    def get_prompt(self, prompt_id: str) -> Prompt:
        return self.prompts.get(prompt_id)

    def list_prompts(self) -> List[Prompt]:
        return list(self.prompts.values())

    def remove_prompt(self, prompt_id: str):
        if prompt_id in self.prompts:
            del self.prompts[prompt_id]
            self._log(f"Removed prompt with ID {prompt_id}")

    def optimize_prompt(self, prompt_id: str, optimization_fn):
        prompt = self.get_prompt(prompt_id)
        if prompt:
            optimized_template = optimization_fn(prompt.template)
            prompt.template = optimized_template
            self._log(f"Optimized prompt {prompt_id}")

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [PromptManager] {message}")
