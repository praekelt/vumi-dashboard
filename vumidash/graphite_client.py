"""MetricSource for retrieving metrics from Graphite."""

from twisted.web.client import Agent
from vumidash.base import MetricSource


class GraphiteClient(MetricSource):
    """Read metrics from Graphite."""

    def __init__(self, url):
        self.url = url
