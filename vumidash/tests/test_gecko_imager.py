"""Tests for vumidash.gecko_imager."""

import os

from twisted.trial import unittest
from twisted.internet.defer import Deferred, inlineCallbacks
from vumidash import gecko_imager
from vumidash.gecko_imager import (DashboardImager, DashboardCache,
                                   GeckoImageServer)


class TestDashboardImager(unittest.TestCase):

    def setUp(self):
        remote = os.environ.get("VUMIDASH_SELENIUM_REMOTE")
        if remote is None:
            raise unittest.SkipTest("Define VUMIDASH_SELENIUM_REMOTE"
                                    " to run DashboardImager tests.")
        # TODO: implement proper test HTTP service
        url = "http://foo/"
        self.imager = DashboardImager(remote, url)

    def test_generate_image(self):
        png = self.imager.generate_image()
        self.assertEqual(png[:8], "\x89PNG\r\n\x1A\n")


class DummyImager(DashboardImager):
    """Dummy imager for testing."""

    def generate_png(self):
        return "A dummy PNG."


class TestDashboardCache(unittest.TestCase):

    def setUp(self):
        self.patch(gecko_imager, 'DashboardImager', DummyImager)
        self.cache = DashboardCache("http://example.com/selenium", {
            "dash1": "http://example.com/dash1",
            }, 5)
        self.cache.start()

    def tearDown(self):
        self.cache.stop()

    @inlineCallbacks
    def test_generate_image(self):
        d = Deferred()
        imager = self.cache.dashboards["dash1"]
        self.cache._generate_image(d, imager)
        png = yield d
        self.assertEqual(png, "A dummy PNG.")

    def test_refresh_images(self):
        pass

    def test_get_png(self):
        pass


class TestGeckoImageServer(unittest.TestCase):

    @inlineCallbacks
    def setUp(self):
        self.patch(gecko_imager, 'DashboardImager', DummyImager)
        dashboards = {}
        self.service = GeckoImageServer(0, "http://example.com/selenium",
                                        dashboards, 30)
        yield self.service.startService()
        addr = self.service.webserver.getHost()
        self.url = "http://%s:%s/" % (addr.host, addr.port)

    @inlineCallbacks
    def tearDown(self):
        yield self.service.stopService()

    def test_something(self):
        pass
