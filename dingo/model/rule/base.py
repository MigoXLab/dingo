from typing import List

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.model.modelres import ModelRes


class BaseRule:
    metric_type: str  # This will be set by the decorator
    group: List[str]  # This will be set by the decorator
    dynamic_config: EvaluatorRuleArgs
    
    # Quality label constants
    LABEL_QUALITY_GOOD = "QUALITY_GOOD"  # Indicates pass the quality check
    LABEL_QUALITY_BAD_PREFIX = "QUALITY_BAD_"  # Indicates not pass the quality check

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        """Evaluate the quality of input data
        
        Subclasses should override this method to implement specific evaluation logic.
        
        Standard implementation pattern:
        ```python
        res = ModelRes()
        
        # Check if there are quality issues
        if issue_detected:
            res.eval_status = True  # True indicates an issue was found
            res.eval_details = {
                "label": ["issue label"],
                "metric": ["rule name"],
                "reason": ["issue description"]
            }
        else:
            res.eval_details = {
                "label": [cls.LABEL_QUALITY_GOOD]
            }
        
        return res
        ```
        
        Args:
            input_data: Data object to be evaluated
            
        Returns:
            ModelRes: Evaluation result object
        """
        # Default implementation: subclasses must override this method
        raise NotImplementedError()
