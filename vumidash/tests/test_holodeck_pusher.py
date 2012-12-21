"""Test the Holodeck data pusher."""

from datetime import timedelta

from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks

from vumidash.dummy_client import DummyClient
from vumidash.holodeck_pusher import (
    HoloSample, HoloSamples, HolodeckPusher)


class TestHoloSample(unittest.TestCase):
    def test_create(self):
        s = HoloSample("gecko-name", "holo-name")
        self.assertEqual(s.gecko, "gecko-name")
        self.assertEqual(s.holo, "holo-name")
        self.assertEqual(s.step_dt, timedelta(60))
        self.assertEqual(s.from_dt, timedelta(-60))
        self.assertEqual(s.until_dt, timedelta(0))

    def test_create_non_default_step_dt(self):
        s = HoloSample("gecko-name", "holo-name", step_dt=30)
        self.assertEqual(s.step_dt, timedelta(30))
        self.assertEqual(s.from_dt, timedelta(-30))

    def test_eq(self):
        s1 = HoloSample("gecko-name", "holo-name")
        s2 = HoloSample("gecko-name", "holo-name")
        self.assertEqual(s1, s2)

    def test_not_eq(self):
        s1 = HoloSample("gecko-name", "holo-name")
        s2 = HoloSample("gecko-name", "holo-name", step_dt=30)
        self.assertNotEqual(s1, s2)

    def test_from_config(self):
        s = HoloSample.from_config({
                "gecko": "gecko-name",
                "holo": "holo-name",
        })
        self.assertEqual(s, HoloSample("gecko-name", "holo-name"))


class DummyTxClient(object):
    def __init__(self, server):
        self.server = server
        self.sends = []

    def send(self, api_key, samples, timestamp):
        self.sends.append((self.server, api_key, samples, timestamp))


class TestHoloSamples(unittest.TestCase):
    def setUp(self):
        import vumidash.holodeck_pusher
        self.dummy_client = None
        self.patch(vumidash.holodeck_pusher, 'TxClient', self.mk_client)
        self.samples = [
            HoloSample("test.gecko1", "holo1"),
            HoloSample("test.gecko2", "holo2"),
        ]
        self.hs = HoloSamples("server", "api_key", 60, self.samples)
        self.metrics_source = DummyClient()

    def mk_client(self, server):
        self.dummy_client = DummyTxClient(server)
        return self.dummy_client

    def test_create(self):
        self.assertEqual(self.hs.server, "server")
        self.assertEqual(self.hs.api_key, "api_key")
        self.assertEqual(self.hs.frequency, 60)
        self.assertEqual(self.hs.samples, self.samples)

    def test_next(self):
        self.assertEqual(self.hs.next(0), 60)
        self.assertEqual(self.hs.next(1), 60)
        self.assertEqual(self.hs.next(59), 60)
        self.assertEqual(self.hs.next(60), 120)

    @inlineCallbacks
    def test_push(self):
        yield self.hs.push(120.0, self.metrics_source)


class TestHolodeckPusher(unittest.TestCase):
    def test_todo(self):
        self.fail("No tests yet.")
