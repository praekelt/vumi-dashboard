"""Test the server of Geckoboard data."""

import json
from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks, succeed
from vumidash.graphite_client import GraphiteClient


TESTDATA_FULL = """[{"target": "foo.count.sum", "datapoints": [
        [35.0, 1362204000], [1206.0, 1362204900], [1230.0, 1362205800],
        [1295.0, 1362206700], [1553.0, 1362207600], [1239.0, 1362208500],
        [1406.0, 1362209400], [1358.0, 1362210300], [64.0, 1362211200]]}]"""

TESTDATA_EMPTY = "[]"


class TestGraphiteClient(unittest.TestCase):

    def setUp(self):
        self.testdata_full = json.loads(TESTDATA_FULL)
        self.testdata_empty = json.loads(TESTDATA_EMPTY)

    def set_up_client(self, data):
        client = GraphiteClient(None)
        client.make_graphite_request = lambda *a: succeed(data)
        return client

    @inlineCallbacks
    def test_latest_full(self):
        client = self.set_up_client(self.testdata_full)
        data = yield client.get_latest("foo.count.sum", None, None, None)
        self.assertEqual(data, (35.0, 64.0))

    @inlineCallbacks
    def test_latest_empty(self):
        client = self.set_up_client(self.testdata_empty)
        data = yield client.get_latest("foo.count.sum", None, None, None)
        self.assertEqual(data, (None, None))

    @inlineCallbacks
    def test_history_full(self):
        client = self.set_up_client(self.testdata_full)
        data = yield client.get_history("foo.count.sum", -7200, 0, 900)
        self.assertEqual(len(data), 9)

    @inlineCallbacks
    def test_history_empty(self):
        client = self.set_up_client(self.testdata_empty)
        data = yield client.get_history("foo.count.sum", -7200, 0, 900)
        self.assertEqual(len(data), 0)
