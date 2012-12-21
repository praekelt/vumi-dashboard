"""MetricSource that serves dummy data."""

import random
from vumidash.base import MetricSource, UnknownMetricError


class DummyClient(MetricSource):
    """Serve dummy data."""

    def __init__(self):
        self.latest = None
        self.metric_prefix = "test"
        self.prev_values = {}  # map of metrics to previous values

    def new_value(self, metric):
        values = self.prev_values.setdefault(metric, [])
        values.insert(0, random.uniform(0, 100))
        return values

    def get_latest(self, metric, start, end, summary_size, skip_nulls=True):
        values = self.get_history(metric, start, end, summary_size, skip_nulls)
        return values[0], values[-1]

    def get_history(self, metric, start, end, summary_size, skip_nulls=True):
        if not metric.startswith(self.metric_prefix):
            raise UnknownMetricError("Uknown metric %r" % (metric,))
        steps = int(self.total_seconds((-start) - (-end))
                    / float(self.total_seconds(summary_size)))
        values = self.new_value(metric)
        while len(values) < steps:
            values = self.new_value(metric)
        return values[:steps]
