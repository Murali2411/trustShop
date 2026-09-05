from .base import BasePipeline,PipelineResult
from .live_sources import CarDekhoSource
class CarPipeline(BasePipeline):
    category='car'
    def __init__(self): self.source=CarDekhoSource()
    def search(self,catalog,query):
        items,meta=self.source.search(query)
        return PipelineResult(items,meta.get('upgrade'),meta.get('explanation','Live CarDekho search.'))
