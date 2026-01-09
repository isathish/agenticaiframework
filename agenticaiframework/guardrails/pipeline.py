"""
Guardrail Pipeline for chaining multiple guardrails with conditional logic.

Features:
- Sequential and parallel execution
- Conditional branching
- Early termination
- Aggregated results
"""

from typing import Dict, Any, List, Union, Callable, Optional
from datetime import datetime

from .types import GuardrailAction
from .core import Guardrail


class GuardrailPipeline:
    """
    Pipeline for chaining multiple guardrails with conditional logic.
    
    Features:
    - Sequential and parallel execution
    - Conditional branching
    - Early termination
    - Aggregated results
    """
    
    def __init__(self, name: str):
        self.name = name
        self.stages: List[Dict[str, Any]] = []
        self.execution_log: List[Dict[str, Any]] = []
    
    def add_stage(self,
                  guardrails: List[Union[Guardrail, Any]],
                  mode: str = "all",
                  condition: Optional[Callable[[Dict], bool]] = None,
                  on_failure: GuardrailAction = GuardrailAction.BLOCK):
        """
        Add a stage to the pipeline.
        
        Args:
            guardrails: List of guardrails to run in this stage
            mode: "all" (all must pass), "any" (any must pass), "majority"
            condition: Optional condition to execute this stage
            on_failure: Action to take on failure
        """
        self.stages.append({
            'guardrails': guardrails,
            'mode': mode,
            'condition': condition,
            'on_failure': on_failure
        })
    
    def execute(self, data: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute the guardrail pipeline.
        
        Returns:
            Dict with overall result and stage-by-stage breakdown
        """
        context = context or {}
        results = {
            'pipeline': self.name,
            'is_valid': True,
            'stages_executed': 0,
            'stages_passed': 0,
            'stages_failed': 0,
            'violations': [],
            'actions_taken': [],
            'timestamp': datetime.now().isoformat()
        }
        
        for i, stage in enumerate(self.stages):
            # Check condition
            if stage['condition'] and not stage['condition'](context):
                continue
            
            results['stages_executed'] += 1
            stage_results = self._execute_stage(stage, data)
            
            if stage_results['passed']:
                results['stages_passed'] += 1
            else:
                results['stages_failed'] += 1
                results['violations'].extend(stage_results['violations'])
                results['actions_taken'].append({
                    'stage': i,
                    'action': stage['on_failure'].value
                })
                
                if stage['on_failure'] == GuardrailAction.BLOCK:
                    results['is_valid'] = False
                    break
        
        self.execution_log.append(results)
        return results
    
    def _execute_stage(self, stage: Dict, data: Any) -> Dict[str, Any]:
        """Execute a single stage."""
        guardrails = stage['guardrails']
        mode = stage['mode']
        
        passed_count = 0
        violations = []
        
        for guardrail in guardrails:
            if hasattr(guardrail, 'validate'):
                # Standard guardrail
                if guardrail.validate(data):
                    passed_count += 1
                else:
                    violations.append({
                        'guardrail': guardrail.name if hasattr(guardrail, 'name') else str(guardrail),
                        'data_preview': str(data)[:100]
                    })
            elif hasattr(guardrail, 'check'):
                # Safety guardrail
                result = guardrail.check(data)
                if result.get('is_safe', True):
                    passed_count += 1
                else:
                    violations.extend(result.get('violations', []))
        
        # Determine if stage passed based on mode
        total = len(guardrails)
        if mode == "all":
            passed = passed_count == total
        elif mode == "any":
            passed = passed_count > 0
        elif mode == "majority":
            passed = passed_count > total / 2
        else:
            passed = passed_count == total
        
        return {
            'passed': passed,
            'passed_count': passed_count,
            'total': total,
            'violations': violations
        }


__all__ = ['GuardrailPipeline']
