# -*- test-case-name: vumidash.tests.test_graphite_client -*-

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
    if not response:
        response = [{'datapoints': []}]
    datapoints = response[0]['datapoints']
    # Put time first and convert to milliseconds.
    datapoints = [(t * 1000, v) for v, t in datapoints]
    return datapoints


def summary_filter(series):
    return series


def filter_datapoints(series):
    return [(t, v) for t, v in series if v is not None]


def filter_nulls_as_zeroes(series):
    return [(t, v) if v is not None else (t, 0.0) for t, v in series]


def filter_latest(series):
    if not series:
        # Let's not crash if we have no data.
        series = [(None, None)]
    return series[0][1], series[-1][1]


def avg(series):
    return sum(series) / len(series)


class GraphiteClient(MetricSource):
    """Read metrics from Graphite."""

    metric_template = 'summarize(%s, "%s", "%s")'

    def __init__(self, url):
        self.url = url

    def make_graphite_request(self, target, start, end):
        t_from = self.make_graphite_timedelta(start)
        t_until = self.make_graphite_timedelta(end)
        agent = Agent(reactor)
        url = '%s/render?format=json&target=%s&from=%s&until=%s' % (
            self.url, quote(target), t_from, t_until)
        print "URL:", url
        d = agent.request('GET', url)
        return d.addCallback(GraphiteDataReader.get_response)

    def make_graphite_timedelta(self, dt):
        totalseconds = self.total_seconds(dt)
        if totalseconds == 0:
            # Having "-0" here is important.
            return '-0s'
        return '%ds' % totalseconds

    def summarise(self, series, metric, summary_size):
        if not series:
            return []

        agg_method = metric.rstrip(')').split('.')[-1]
        if metric.startswith("integral("):
            agg_method = 'max'
        agg_func = {
            'min': min,
            'max': max,
            'sum': sum,
        }.get(agg_method, avg)

        summary_size *= 1000
        summarised_series = []

        last_time = series[0][0] - (series[0][0] % summary_size)
        summary_block = []

        while series:
            time, value = series.pop(0)
            if time >= last_time + summary_size:
                summarised_series.append((last_time, agg_func(summary_block)))
                last_time += summary_size
                summary_block = []
            summary_block.append(value)
        summarised_series.append((last_time, agg_func(summary_block)))

        return summarised_series

    def get_series(self, metric, start, end, skip_nulls=True):
        d = self.make_graphite_request(metric, start, end)
        point_filter = (filter_datapoints if skip_nulls
                        else filter_nulls_as_zeroes)
        return d.addCallback(all_datapoints).addCallback(point_filter)

    def get_latest(self, metric, start, end, summary_size, skip_nulls=True):
        d = self.get_series(metric, start, end, skip_nulls)
        return d.addCallback(filter_latest)

    def get_history(self, metric, start, end, summary_size, skip_nulls=True):
        d = self.get_series(metric, start, end, skip_nulls)
        if summary_size is not None:
            d.addCallback(self.summarise, metric, summary_size)
        return d
