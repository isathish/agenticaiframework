"""
Model Router.

Intelligent model router for selecting optimal models based on task requirements:
- Task-based routing (simple vs complex)
- Cost optimization
- Latency optimization  
- Capability matching
- SLM/RLM automatic selection
"""

import time
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from collections import defaultdict

from .types import ModelTier, ModelCapability, ModelConfig
from .registry import MODEL_REGISTRY

if TYPE_CHECKING:
    from .manager import LLMManager


class ModelRouter:
    """
    Intelligent model router for selecting optimal models based on task requirements.
    
    Features:
    - Task-based routing (simple vs complex)
    - Cost optimization
    - Latency optimization  
    - Capability matching
    - SLM/RLM automatic selection
    """
    
    def __init__(self, llm_manager: 'LLMManager'):
        self.llm_manager = llm_manager
        self.routing_history: List[Dict[str, Any]] = []
    
    def route(self,
              prompt: str,
              required_capabilities: List[ModelCapability] = None,
              preferred_tier: ModelTier = None,
              max_cost: float = None,
              max_latency_ms: float = None,
              prefer_reasoning: bool = False) -> Optional[str]:
        """
        Route to optimal model based on requirements.
        
        Args:
            prompt: The input prompt (used for complexity estimation)
            required_capabilities: Required model capabilities
            preferred_tier: Preferred model tier
            max_cost: Maximum cost per 1K tokens (input + output)
            max_latency_ms: Maximum acceptable latency
            prefer_reasoning: Whether to prefer reasoning models
            
        Returns:
            Selected model name or None if no suitable model found
        """
        candidates = []
        required_capabilities = required_capabilities or []
        
        for model_name in self.llm_manager.list_models():
            config = self._get_model_config(model_name)
            if not config:
                continue
            
            # Filter by capabilities
            if required_capabilities:
                if not all(cap in config.capabilities for cap in required_capabilities):
                    continue
            
            # Filter by tier
            if preferred_tier and config.tier != preferred_tier:
                continue
            
            # Filter by cost
            total_cost = config.cost_per_1k_input + config.cost_per_1k_output
            if max_cost and total_cost > max_cost:
                continue
            
            # Filter by latency
            if max_latency_ms and config.latency_ms_avg > max_latency_ms:
                continue
            
            candidates.append((model_name, config, total_cost))
        
        if not candidates:
            return self.llm_manager.active_model
        
        # Score and rank candidates
        scored = []
        for model_name, config, total_cost in candidates:
            score = 0.0
            
            # Prefer reasoning models if requested
            if prefer_reasoning and config.tier == ModelTier.RLM:
                score += 100
            
            # Prefer SLM for simple tasks (short prompts)
            if len(prompt) < 500 and config.tier == ModelTier.SLM:
                score += 50
            
            # Cost efficiency (lower is better)
            score -= total_cost * 10
            
            # Latency (lower is better)
            score -= config.latency_ms_avg / 1000
            
            scored.append((model_name, score))
        
        # Select best model
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = scored[0][0]
        
        # Record routing decision
        self.routing_history.append({
            'timestamp': time.time(),
            'prompt_length': len(prompt),
            'required_capabilities': [c.value for c in required_capabilities],
            'preferred_tier': preferred_tier.value if preferred_tier else None,
            'selected_model': selected,
            'candidates_count': len(candidates)
        })
        
        return selected
    
    def _get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """Get model configuration."""
        # Check registry first
        if model_name in MODEL_REGISTRY:
            return MODEL_REGISTRY[model_name]
        
        # Build from metadata
        metadata = self.llm_manager.model_metadata.get(model_name, {})
        if metadata:
            return ModelConfig(
                name=model_name,
                tier=ModelTier(metadata.get('tier', 'llm')),
                capabilities=[ModelCapability(c) for c in metadata.get('capabilities', [])],
                max_tokens=metadata.get('max_tokens', 4096),
                context_window=metadata.get('context_window', 8192),
                cost_per_1k_input=metadata.get('cost_per_1k_input', 0),
                cost_per_1k_output=metadata.get('cost_per_1k_output', 0),
                latency_ms_avg=metadata.get('latency_ms_avg', 1000),
                provider=metadata.get('provider', 'unknown')
            )
        
        return None
    
    def select_for_reasoning(self) -> Optional[str]:
        """Select best model for reasoning/chain-of-thought tasks."""
        return self.route(
            prompt="",
            required_capabilities=[ModelCapability.REASONING],
            prefer_reasoning=True
        )
    
    def select_for_speed(self) -> Optional[str]:
        """Select fastest model (typically SLM)."""
        return self.route(
            prompt="",
            preferred_tier=ModelTier.SLM,
            max_latency_ms=500
        )
    
    def select_for_cost(self) -> Optional[str]:
        """Select most cost-effective model."""
        return self.route(
            prompt="",
            max_cost=0.001  # Max $0.001 per 1K tokens
        )
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        if not self.routing_history:
            return {'total_routes': 0}
        
        model_counts = defaultdict(int)
        for route in self.routing_history:
            model_counts[route['selected_model']] += 1
        
        return {
            'total_routes': len(self.routing_history),
            'model_distribution': dict(model_counts),
            'avg_candidates': sum(r['candidates_count'] for r in self.routing_history) / len(self.routing_history)
        }


__all__ = ['ModelRouter']
