from datetime import datetime, timedelta
from .pipeline import PipelineStage, EndOfPayload
from ...web import encoder

MIN_UPDATE_TIME = timedelta(seconds=1)


class ReportProgress(PipelineStage):
    def __init__(self, progressobj):
        """Initialize the write progress stage.

        Arguments:
            progressobj (object): An object with a write_progress function
        """
        super(ReportProgress, self).__init__()

        self._rows_written = 0
        self._last_write = datetime.utcnow()
        self._progressobj = progressobj

    def process(self, payload):
        """Pipeline stage that writes SSE progress"""
        if payload != EndOfPayload:
            # Keep unmatched values at the end
            elapsed = datetime.utcnow() - self._last_write
            if elapsed > MIN_UPDATE_TIME:
                progress = encoder.json_sse_pack({"event": "progress", "data": {"rows": self._rows_written}})
                self._progressobj.write_progress(progress)
                self._last_write = datetime.utcnow()

            self._rows_written += 1
        else:
            progress = encoder.json_sse_pack({"event": "progress", "data": {"rows": self._rows_written, "status": "finalizing"}})
            self._progressobj.write_progress(progress)

        self.emit(payload)
