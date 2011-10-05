"""Test the server of Geckoboard data."""

import json
from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import getPage
from vumidash.gecko_server import GeckoServer
from vumidash.base import MetricSource


class DummySource(MetricSource):
    def get_latest(self, metric_name):
        if metric_name == 'foo':
            return 5, 6
        else:
            raise ValueError("Unknown metric")

    def get_history(self, metric_name):
        if metric_name == 'foo':
            return [1, 2, 3, 4, 5]
        else:
            raise ValueError("Unknown metric")


class TestGeckoServer(unittest.TestCase):

    @inlineCallbacks
    def setUp(self):
        self.metrics_source = DummySource()
        self.service = GeckoServer(self.metrics_source, 0)
        yield self.service.startService()
        addr = self.service.webserver.getHost()
        self.url = "http://%s:%s/" % (addr.host, addr.port)

    @inlineCallbacks
    def tearDown(self):
        yield self.service.stopService()

    @inlineCallbacks
    def get_route_json(self, route):
        data = yield getPage(self.url + route)
        returnValue(json.loads(data))

    @inlineCallbacks
    def test_simple_latest(self):
        data = yield self.get_route_json('latest?metric=foo')
        self.assertTrue('item' in data)

    @inlineCallbacks
    def test_simple_history(self):
        data = yield self.get_route_json('history?metric=foo')
        self.assertTrue('title' in data)
