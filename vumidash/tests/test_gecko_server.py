"""Test the server of Geckoboard data."""

import json
import copy
from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import getPage
from vumidash.gecko_server import GeckoServer
from vumidash.base import MetricSource


class DummySource(MetricSource):
    def __init__(self, testdata):
        self.testdata = testdata

    def get_latest(self, metric_name, summary_size):
        data = self.testdata.get(metric_name)
        if not data:
            raise ValueError("Unknown metric")
        return data[0], data[1] if len(data) > 1 else None

    def get_history(self, metric_name, start, end, summary_size):
        data = self.testdata.get(metric_name)
        if not data:
            raise ValueError("Unknown metric")
        steps = int(self.total_seconds(end - start) /
                    float(self.total_seconds(summary_size)))
        return data[:steps]


class TestGeckoServer(unittest.TestCase):

    TESTDATA = {
        'foo': [1, 2, 3, 4, 5],
        'bar': [6, 7, 8, 9, 10],
        }

    @inlineCallbacks
    def setUp(self):
        self.testdata = copy.deepcopy(self.TESTDATA)
        self.metrics_source = DummySource(self.testdata)
        self.service = GeckoServer(self.metrics_source, 0)
        yield self.service.startService()
        addr = self.service.webserver.getHost()
        self.url = "http://%s:%s/" % (addr.host, addr.port)

    @inlineCallbacks
    def tearDown(self):
        yield self.service.stopService()

    @inlineCallbacks
    def get_route_json(self, route):
        data = yield getPage(self.url + route, timeout=1)
        returnValue(json.loads(data))

    def check_series(self, json, series_dict):
        series_map = dict((series['name'], series)
                          for series in json['series'])
        for name, expected_data in series_dict.items():
            series = series_map[name]
            self.assertEqual(series['data'], expected_data)
            self.assertEqual(series['type'], 'line')
        self.assertEqual(len(series_map), len(series_dict))

    @inlineCallbacks
    def test_simple_latest(self):
        data = yield self.get_route_json('latest?metric=foo')
        self.assertTrue('item' in data)

    @inlineCallbacks
    def test_simple_history(self):
        data = yield self.get_route_json('history?metric=foo')
        self.assertTrue('title' in data)
        self.check_series(data, {'foo': self.testdata['foo']})

    @inlineCallbacks
    def test_multiple_history(self):
        data = yield self.get_route_json('history?metric=foo&metric=bar')
        self.assertTrue('title' in data)
        self.check_series(data, {
            'foo': self.testdata['foo'],
            'bar': self.testdata['bar'],
            })

    @inlineCallbacks
    def test_history_with_ranges(self):
        data = yield self.get_route_json('history?metric=foo'
                                         '&from=-3s&until=-0s&step=1s')
        self.assertTrue('title' in data)
        self.check_series(data, {'foo': self.testdata['foo'][:3]})

    @inlineCallbacks
    def test_history_with_ymin(self):
        data = yield self.get_route_json('history?metric=foo&ymin=-3.2')
        self.assertTrue('title' in data)
        self.assertEqual(-3.2, data['yAxis']['min'])
