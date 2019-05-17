from abc import ABCMeta, abstractmethod

# Placeholder value to indicate that the end of data has been reached
EndOfPayload = object()


class PipelineStage(object):
    __metaclass__ = ABCMeta

    """Represents a single stage in a data-processing pipeline"""

    def __init__(self):
        self._next = None

    def pipe(self, next_stage):
        """Add another stage to the tail of the pipeline
        
        Arguments:
            next_stage (PipelineStage): The new tail of the pipeline        
        """
        if self._next:
            self._next.pipe(next_stage)
        else:
            self._next = next_stage

    def emit(self, payload):
        """Emit a value to the next stage in the pipeline. 

        Raises a RuntimeError if there are no more stages in the pipeline.

        Arguments:
            payload: The payload to emit to the next pipeline stage
        """
        if not self._next:
            raise RuntimeError("Last stage of pipeline is emitting a value")
        self._next.process(payload)

    @abstractmethod
    def process(self, payload):
        """Process an incoming payload in the pipeline.

        Arguments:
            payload: The payload from the previous pipeline stage
        """
        pass
