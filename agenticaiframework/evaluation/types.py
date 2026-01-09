"""
Evaluation types and base classes.

This module contains the core enums and dataclasses used across
the evaluation system.
"""

from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum


class EvaluationType(Enum):
    """Types of evaluation."""
    OFFLINE = "offline"
    ONLINE = "online"
    SHADOW = "shadow"
    CANARY = "canary"


@dataclass
class EvaluationResult:
    """Result of an evaluation."""
    evaluation_id: str
    evaluation_type: EvaluationType
    input_data: Any
    expected_output: Any
    actual_output: Any
    scores: Dict[str, float]
    metadata: Dict[str, Any]
    timestamp: float
    latency_ms: float
    
    @property
    def passed(self) -> bool:
        """Check if evaluation passed all criteria."""
        return all(score >= 0.5 for score in self.scores.values())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'evaluation_id': self.evaluation_id,
            'evaluation_type': self.evaluation_type.value,
            'scores': self.scores,
            'passed': self.passed,
            'metadata': self.metadata,
            'timestamp': self.timestamp,
            'latency_ms': self.latency_ms
        }


__all__ = ['EvaluationType', 'EvaluationResult']
