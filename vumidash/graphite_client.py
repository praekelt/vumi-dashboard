"""MetricSource for retrieving metrics from Graphite."""

import json
from StringIO import StringIO
from urllib import quote

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
    return (response or [{'datapoints': []}])[0]['datapoints']


def filter_datapoints(response):
    return [(v, t) for v, t in all_datapoints(response) if v is not None]


def filter_latest(response):
    return ([(None, None), (None, None)] + filter_datapoints(response))[-2:]


class GraphiteClient(MetricSource):
    """Read metrics from Graphite."""

    metric_template = 'summarize(%s, "5min")'

    def __init__(self, url):
        self.url = url

    def make_graphite_request(self, target, t_from, t_until):
        agent = Agent(reactor)
        url = '%s/render?format=json&target=%s&from=%s&until=%s' % (
            self.url, quote(self.format_metric(target)), t_from, t_until)
        print "URL:", url
        d = agent.request('GET', url)
        return d.addCallback(GraphiteDataReader.get_response)

    def format_metric(self, metric):
        return self.metric_template % (metric,)

    def get_latest(self, metric):
        d = self.make_graphite_request(metric, '-15min', '-0s')
        return d.addCallback(filter_latest)

    def get_history(self, metric):
        d = self.make_graphite_request(metric, '-24h', '-0s')
        return d.addCallback(filter_datapoints)
