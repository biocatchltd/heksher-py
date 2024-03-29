import json
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CreateRuleParams:
    setting: str  # The name of the configuration
    feature_values: Dict[str, str]
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)

    def json(self):
        return json.dumps({
            'setting': self.setting,
            'feature_values': self.feature_values,
            'value': self.value,
            'metadata': self.metadata
        })
