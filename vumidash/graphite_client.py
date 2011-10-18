"""MetricSource for retrieving metrics from Graphite."""

import json
from StringIO import StringIO
from urllib import quote
from datetime import timedelta

from twisted.web.client import Agent
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol

from vumidash.base import MetricSource


class GraphiteDataReader(Protocol):
    def __init__(self, deferred):
        self.deferred = deferred
        self.stringio = StringIO()

    def dataReceived(self, data):
        self.stringio.write(data)

    def connectionLost(self, reason):
        data = self.stringio.getvalue()
        self.deferred.callback(json.loads(data))

    @classmethod
    def get_response(cls, response):
        finished = Deferred()
        response.deliverBody(cls(finished))
        return finished


def all_datapoints(response):
    if not response:
        response = [{'datapoints': []}]
    datapoints = response[0]['datapoints']
    # Put time first and convert to milliseconds.
    datapoints = [(t * 1000, v) for v, t in datapoints]
    return datapoints


def filter_datapoints(response):
    return [(t, v) for t, v in all_datapoints(response) if v is not None]


def filter_nulls_as_zeroes(response):
    return [(t, v) if v is not None else (t, 0.0)
            for t, v in all_datapoints(response)]


def filter_latest(series):
    return series[0][1], series[-1][1]


class GraphiteClient(MetricSource):
    """Read metrics from Graphite."""

    metric_template = 'summarize(%s, "%s", "%s")'

    def __init__(self, url):
        self.url = url

    def make_graphite_request(self, target, start, end, summary_size):
        t_from = self.make_graphite_timedelta(start)
        t_until = self.make_graphite_timedelta(end)
        t_summary = self.make_graphite_timedelta(summary_size)
        agent = Agent(reactor)
        url = '%s/render?format=json&target=%s&from=%s&until=%s' % (
            self.url, quote(self.format_metric(target, t_summary)),
            t_from, t_until)
        print "URL:", url
        d = agent.request('GET', url)
        return d.addCallback(GraphiteDataReader.get_response)

    def make_graphite_timedelta(self, dt):
        totalseconds = self.total_seconds(dt)
        if totalseconds == 0:
            # Having "-0" here is important.
            return '-0s'
        return '%ds' % totalseconds

    def format_metric(self, metric, t_summary):
        agg_method = "avg"
        last_bit = metric.rstrip(')').split('.')[-1]
        if last_bit in ('max', 'min', 'sum'):
            agg_method = last_bit
        if metric.startswith("integral("):
            agg_method = 'max'
        return self.metric_template % (metric, t_summary, agg_method)

    def get_latest(self, metric, start, end, summary_size, skip_nulls=True):
        d = self.get_history(metric, start, end, summary_size, skip_nulls)
        return d.addCallback(filter_latest)

    def get_history(self, metric, start, end, summary_size, skip_nulls=True):
        d = self.make_graphite_request(metric, start, end, summary_size)
        point_filter = (filter_datapoints if skip_nulls
                        else filter_nulls_as_zeroes)
        return d.addCallback(point_filter)
