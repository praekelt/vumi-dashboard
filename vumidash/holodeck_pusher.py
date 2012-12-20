# -*- test-case-name: vumidash.tests.test_holodeck_pusher -*-

"""Service that pushes metrics to Holodeck."""

import heapq
import math
from datetime import datetime

from twisted.application.service import Service
from twisted.internet.defer import inlineCallbacks, gatherResults
from twisted.python import log
from twisted.internet import reactor
from photon.txclient import TxClient


class HoloSample(object):
    def __init__(self, gecko, holo):
        self.gecko = gecko
        self.holo = holo

    @classmethod
    def from_config_list(cls, config_list):
        return [cls(item['gecko'], item['holo']) for item in config_list]


class HoloSamples(object):
    def __init__(self, server, api_key, frequency, samples):
        self.server = server
        self.api_key = api_key
        self.frequency = float(frequency)
        self.samples = samples

    def next(self, now):
        return (math.floor(now / self.freq) + 1) * self.freq

    @inlineCallbacks
    def push(self, now, metrics_source):
        client = TxClient(self.server)
        holo_samples = []
        from_dt, until_dt, step_dt = "?", "?", "?"
        for sample in self.samples:
            value = yield metrics_source.get_latest(sample.gecko, from_dt,
                                                    until_dt, step_dt)
            holo_samples.append([sample.holo, value])
        yield client.send(samples=holo_samples,
                          api_key=self.api_key,
                          timestamp=datetime.fromtimestamp(now))


class HolodeckPusher(object):
    """Reads metrics defined in config from a metric source and pushes
    them to Holodeck.

    :type metric_source: :class:`vumidash.base.MetricSource`
    :param metric_source: Source to read metrics from.

    :param dict config: Cofiguration dictionary. Top-level keys are
        Holodeck server URLs. Second-level keys are API keys. Each API
        key is associated with a frequency and a list of metrics
        (Holodeck samples). A metric consists of a geckoboard metric
        definition and a Holodeck sample name. E.g.:

        { "http://holodeck1.example.com": {
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
        }}
    """

    clock = reactor  # testing hook

    def __init__(self, metrics_source, config):
        self.metrics_source = metrics_source
        self.samples = []
        self._next_call = None
        self._next_heap = None
        self._waiting = []
        self._parse_config(config)

    def _parse_config(self, config):
        for server, server_defn in config.iteritems():
            for api_key, sample_defn in server_defn.iteritems():
                frequency = sample_defn['frequency']
                samples = HoloSample.from_config_list(sample_defn['samples'])
                self.samples.append(HoloSamples(server, api_key, frequency,
                                                samples))

    def _create_next_heap(self):
        now = self.clock.seconds()
        self._next_heap = [(sample.next(now), sample) for sample in
                           self.samples]
        heapq.heapify(self._next_heap)

    def _call_next_later(self):
        next_time, sample = heapq.heappop(self._next_heap)
        now = self.clock.seconds()
        self._next_call = self.clock.callLater(
            next_time - now, self._process_next, next_time, sample)

    def _process_next(self, now, sample):
        heapq.heappush(self._next_heap, (sample.next(now), sample))
        try:
            d = sample.push(now, self.metrics_source)
            self._waiting.append(d)
        except Exception:
            log.err()
        self._call_next_later()

    def start(self):
        if not self._samples:
            return
        self._create_next_heap()
        self._call_next_later()

    @inlineCallbacks
    def stop(self):
        if self._next_call is not None and self._next_call.active():
            self._next_call.cancel()
        yield gatherResults(self._waiting)


class HolodeckPusherService(Service):
    def __init__(self, metrics_source, config):
        self.holodeck_pusher = HolodeckPusher(metrics_source, config)

    @inlineCallbacks
    def startService(self):
        yield self.holodeck_pusher.start()

    @inlineCallbacks
    def stopService(self):
        yield self.holodeck_pusher.stop()
