from typing import Any, Dict

from pydantic import BaseModel, Field


class CreateRuleParams(BaseModel):
    setting: str  # The name of the configuration
    feature_values: Dict[str, str]
    value: Any
    metadata: Dict[str, str] = Field(default_factory=dict)
