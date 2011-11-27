"""Tests for vumidash.gecko_imager."""

import os

from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks
from vumidash import gecko_imager
from vumidash.gecko_imager import DashboardImager, GeckoImageServer


class TestDashboardImager(unittest.TestCase):

    def setUp(self):
        remote = os.environ.get("VUMIDASH_SELENIUM_REMOTE")
        if remote is None:
            raise unittest.SkipTest("Define VUMIDASH_SELENIUM_REMOTE"
                                    " to run DashboardImager tests.")
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

    def tearDown(self):
        pass

    def test_generate_image(self):
        pass

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
