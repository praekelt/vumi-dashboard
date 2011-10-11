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

    def get_latest(self, metric_name, start, end, summary_size):
        values = self.get_history(metric_name, start, end, summary_size)
        return values[0], values[-1]

    def get_history(self, metric_name, start, end, summary_size,
                    skip_nulls=True):
        data = self.testdata.get(metric_name)
        if not data:
            raise ValueError("Unknown metric")
        steps = int(self.total_seconds(end - start) /
                    float(self.total_seconds(summary_size)))
        values = data[:steps]
        if skip_nulls:
            return [v for v in values if v is not None]
        else:
            return [v if v is not None else 0.0 for v in values]


class TestGeckoServer(unittest.TestCase):

    TESTDATA = {
        'foo': [1, 2, 3, 4, 5],
        'bar': [6, 7, 8, 9, 10],
        'zeroes': [1, 2, None, 3, 4, None, 5],
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
    def test_multiple_latest(self):
        data = yield self.get_route_json('latest?metric=foo&metric=bar')
        self.assertEqual({'item': [{'text': '', 'value': 15},
                                   {'text': '', 'value': 7}]}, data)

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
        data = yield self.get_route_json('history?metric=foo')
        self.assertEqual(None, data['yAxis']['min'])
        data = yield self.get_route_json('history?metric=foo&ymin=-3.2')
        self.assertEqual(-3.2, data['yAxis']['min'])

    @inlineCallbacks
    def test_history_with_markers(self):
        data = yield self.get_route_json('history?metric=foo&markers=false')
        self.assertFalse(data['plotOptions']['line']['marker']['enabled'])
        data = yield self.get_route_json('history?metric=foo&markers=true')
        self.assertTrue(data['plotOptions']['line']['marker']['enabled'])

    @inlineCallbacks
    def test_history_with_labels(self):
        data = yield self.get_route_json('history?metric=foo&label=bar')
        self.check_series(data, {'bar': self.testdata['foo']})

    @inlineCallbacks
    def test_history_with_multiple_labels(self):
        data = yield self.get_route_json('history?metric=foo&label=foolabel'
                                         '&metric=bar&label=barlabel')
        self.check_series(data, {
            'foolabel': self.testdata['foo'],
            'barlabel': self.testdata['bar'],
            })

    @inlineCallbacks
    def test_yaxis_label(self):
        data = yield self.get_route_json('history?metric=foo&ylabel=bar')
        self.assertEqual(data['yAxis']['title']['text'], 'bar')

    @inlineCallbacks
    def test_skip_nulls(self):
        data = yield self.get_route_json('history?metric=zeroes')
        without_nulls = [v for v in self.testdata['zeroes'] if v is not None]
        self.check_series(data, {'zeroes': without_nulls})

        data = yield self.get_route_json('history?metric=zeroes'
                                         '&skip_nulls=false')
        with_nulls_as_zeroes = [v if v is not None else 0.0
                                for v in self.testdata['zeroes']]
        self.check_series(data, {'zeroes': with_nulls_as_zeroes})
