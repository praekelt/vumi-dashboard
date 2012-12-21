# -*- test-case-name: vumidash.tests.test_holodeck_pusher -*-

"""Service that pushes metrics to Holodeck."""

import heapq
import math
from datetime import datetime, timedelta

from twisted.application.service import Service
from twisted.internet.defer import (
    inlineCallbacks, gatherResults, maybeDeferred)
from twisted.python import log
from twisted.internet import reactor
from photon.txclient import TxClient


class HoloSample(object):
    def __init__(self, metric, holo, step_dt=60, from_dt=None,
                 until_dt=None):
        self.metric = metric
        self.holo = holo
        self.step_dt = timedelta(step_dt)
        self.from_dt = (timedelta(from_dt) if from_dt is not None
                        else -self.step_dt)
        self.until_dt = (timedelta(until_dt) if until_dt is not None
                         else timedelta(0))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (self.metric == other.metric and self.holo == other.holo and
                self.step_dt == other.step_dt and
                self.from_dt == other.from_dt and
                self.until_dt == other.until_dt)

    @classmethod
    def from_config(cls, config):
        return cls(**config)


class HoloSamples(object):
    def __init__(self, server, api_key, frequency, samples):
        self.server = server
        self.api_key = api_key
        self.frequency = float(frequency)
        self.samples = samples

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (self.server == other.server and
                self.api_key == other.api_key and
                self.frequency == other.frequency and
                self.samples == other.samples)

    def next(self, now):
        return (math.floor(now / self.frequency) + 1) * self.frequency

    @inlineCallbacks
    def push(self, now, metrics_source):
        client = TxClient(self.server)
        holo_samples = []
        for sample in self.samples:
            d = maybeDeferred(metrics_source.get_latest, sample.metric,
                              sample.from_dt, sample.until_dt, sample.step_dt)
            # replace failures with 0 values
            d.addErrback(lambda f: [0.0])
            values = yield d
            holo_samples.append([sample.holo, values[-1]])
        yield client.send(samples=holo_samples,
                          api_key=self.api_key,
                          timestamp=datetime.fromtimestamp(now))


class HolodeckPusher(object):
    """Reads metrics defined in config from a metric source and pushes
    them to Holodeck.

    :type metric_source: :class:`vumidash.base.MetricSource`
    :param metric_source: Source to read metrics from.

    :type samples: list of :class:`HoloSamples`
    :param samples: List of sample sets to push to Holodeck(s).
    """

    clock = reactor  # testing hook

    def __init__(self, metrics_source, samples):
        self.metrics_source = metrics_source
        self.samples = samples
        self._next_call = None
        self._next_heap = None
        self._waiting = set()

    @classmethod
    def from_config(cls, metrics_source, config):
        """Construct a HolodeckPusher from a metric source and
        a configuration dictionary.

        :type metric_source: :class:`vumidash.base.MetricSource`
        :param metric_source: Source to read metrics from.

        :param dict config: Cofiguration dictionary. Top-level keys
            are Holodeck server URLs. Second-level keys are API
            keys. Each API key is associated with a frequency and a
            list of metrics (Holodeck samples). A metric consists of a
            graphite metric definition (or equivalent for other
            metrics sources) and a Holodeck sample name. E.g.:

            { "http://holodeck1.example.com": {
                "f45c18ff66f8469bdcefe12290dda929": {
                   "frequency": 60,
                   "samples": [
                       {"metric": "my.metric.value", "holo": "Line 1"},
                       {"metric": "my.metric.other", "holo": "Line 2"},
                   ],
                },
                "f45c18ff66f8469bdcefe12290dda92a": {
                   "frequency": 60,
                   "samples": [
                       {"metric": "my.metric.another", "holo": "Gauge 1"},
                   ],
                },
            }}
        """
        samples_list = []
        for server, server_defn in config.iteritems():
            for api_key, sample_defn in server_defn.iteritems():
                frequency = sample_defn['frequency']
                samples = [HoloSample.from_config(s)
                           for s in sample_defn['samples']]
                samples_list.append(HoloSamples(server, api_key, frequency,
                                                samples))
        return cls(metrics_source, samples_list)

    def _add_waiting(self, d):
        self._waiting.add(d)
        d.addBoth(lambda r: self._waiting.discard(d))

    def _create_next_heap(self):
        now = self.clock.seconds()
        self._next_heap = [(sample.next(now), sample) for sample in
                           self.samples]
        heapq.heapify(self._next_heap)

    def _call_next_later(self):
        next_time, sample = heapq.heappop(self._next_heap)
        now = self.clock.seconds()
        self._next_call = self.clock.callLater(
            max(next_time - now, 0), self._process_next, next_time, sample)

    def _process_next(self, now, sample):
        heapq.heappush(self._next_heap, (sample.next(now), sample))
        try:
            d = sample.push(now, self.metrics_source)
            self._add_waiting(d)
        except Exception:
            log.err()
        self._call_next_later()

    def start(self):
        if not self.samples:
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
        self.holodeck_pusher = HolodeckPusher.from_config(metrics_source,
                                                          config)

    @inlineCallbacks
    def startService(self):
        yield self.holodeck_pusher.start()

    @inlineCallbacks
    def stopService(self):
        yield self.holodeck_pusher.stop()
