# -*- test-case-name: vumidash.tests.test_holodeck_pusher -*-

"""Service that pushes metrics to Holodeck."""

from twisted.application.service import Service
from twisted.internet.defer import inlineCallbacks
from photon.txclient import TxClient


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

    def __init__(self, metrics_source, config):
        self.metrics_source = metrics_source
        self._parse_config(config)

    def _parse_config(self, config):
        pass

    def start(self):
        pass

    def stop(self):
        pass


class HolodeckPusherService(Service):
    def __init__(self, metrics_source, config):
        self.holodeck_pusher = HolodeckPusher(metrics_source, config)

    @inlineCallbacks
    def startService(self):
        yield self.holodeck_pusher.start()

    @inlineCallbacks
    def stopService(self):
        yield self.holodeck_pusher.stop()
