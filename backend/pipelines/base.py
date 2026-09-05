from dataclasses import dataclass
from typing import Any, Dict, List
@dataclass
class PipelineResult:
    items: List[Dict[str, Any]]
    upgrade: Dict[str, Any] | None
    explanation: str
class BasePipeline:
    category='unknown'
    def search(self,catalog,query): raise NotImplementedError
