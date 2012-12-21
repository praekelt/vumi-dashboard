"""Test the Holodeck data pusher."""

from datetime import datetime, timedelta

from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet.task import Clock

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

    def get_value(self, metric):
        values = self.metrics_source.prev_values[metric]
        return values[-1]

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
        self.assertEqual(self.dummy_client.sends, [
                ('server', 'api_key', [
                        ['holo1', self.get_value('test.gecko1')],
                        ['holo2', self.get_value('test.gecko2')]],
                 datetime.fromtimestamp(120.0))
        ])

    @inlineCallbacks
    def test_bad_metric(self):
        self.hs.samples.append(HoloSample("bad.gecko", "holo3"))
        yield self.hs.push(120.0, self.metrics_source)
        self.assertEqual(self.dummy_client.sends, [
                ('server', 'api_key', [
                        ['holo1', self.get_value('test.gecko1')],
                        ['holo2', self.get_value('test.gecko2')],
                        ['holo3', 0.0]],
                 datetime.fromtimestamp(120.0))
        ])


class DummySamples(HoloSamples):
    def __init__(self, frequency, expected_metrics_source):
        super(DummySamples, self).__init__("server", "api_key",
                                           frequency, [])
        self.expected_metrics_source = expected_metrics_source
        self.pushes = []
        self.deferreds = []

    def callback_all(self, result=None):
        for d in self.deferreds:
            d.callback(result)

    def push(self, now, metrics_source):
        assert metrics_source is self.expected_metrics_source
        d = Deferred()
        self.pushes.append(now)
        self.deferreds.append(d)
        return d


class TestHolodeckPusher(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.patch(HolodeckPusher, 'clock', self.clock)
        self.metrics_source = object()

    def test_from_config(self):
        hp = HolodeckPusher.from_config(self.metrics_source, {
            "http://holodeck1.example.com": {
                "f45c18ff66f8469bdcefe12290dda929": {
                   "frequency": 60,
                   "samples": [
                       {"gecko": "my.metric.value", "holo": "Line 1"},
                       {"gecko": "my.metric.other", "holo": "Line 2"},
                   ],
                },
                "f45c18ff66f8469bdcefe12290dda92a": {
                   "frequency": 60,
                   "samples": [
                       {"gecko": "my.metric.another", "holo": "Gauge 1"},
                   ],
                },
            }
        })
        self.assertEqual(hp.metrics_source, self.metrics_source)
        self.assertEqual(hp.samples, [
                HoloSamples("http://holodeck1.example.com",
                            "f45c18ff66f8469bdcefe12290dda929",
                            60,
                            [HoloSample("my.metric.value", "Line 1"),
                             HoloSample("my.metric.other", "Line 2")]),
                HoloSamples("http://holodeck1.example.com",
                            "f45c18ff66f8469bdcefe12290dda92a",
                            60,
                            [HoloSample("my.metric.another", "Gauge 1")]),
        ])

    @inlineCallbacks
    def test_sampling(self):
        ds = DummySamples(10, self.metrics_source)
        hp = HolodeckPusher(self.metrics_source, [ds])
        yield hp.start()
        self.assertEqual(ds.pushes, [])
        self.clock.advance(10)
        self.assertEqual(ds.pushes, [10.0])
        self.clock.pump([1.0, 5.0, 4.0, 10.0, 20.0])
        self.assertEqual(ds.pushes, [10.0, 20.0, 30.0, 40.0, 50.0])
        ds.callback_all()
        yield hp.stop()

    @inlineCallbacks
    def test_sampling_with_two_sample_sets(self):
        ds1 = DummySamples(10, self.metrics_source)
        ds2 = DummySamples(5, self.metrics_source)
        hp = HolodeckPusher(self.metrics_source, [ds1, ds2])
        yield hp.start()
        self.assertEqual(ds1.pushes, [])
        self.assertEqual(ds2.pushes, [])
        self.clock.advance(50)
        self.assertEqual(ds1.pushes, [10.0, 20.0, 30.0, 40.0, 50.0])
        self.assertEqual(ds2.pushes, [5.0, 10.0, 15.0, 20.0, 25.0, 30.0,
                                      35.0, 40.0, 45.0, 50.0])
        ds1.callback_all()
        ds2.callback_all()
        yield hp.stop()
