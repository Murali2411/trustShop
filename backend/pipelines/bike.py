from .base import BasePipeline,PipelineResult
from .live_sources import BikeWaleSource
class BikePipeline(BasePipeline):
    category='bike'
    def __init__(self): self.source=BikeWaleSource()
    def search(self,catalog,query):
        items,meta=self.source.search(query)
        return PipelineResult(items,meta.get('upgrade'),meta.get('explanation','Live BikeWale search.'))
