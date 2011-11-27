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

    timeout = 5

    def setUp(self):
        self.patch(gecko_imager, 'DashboardImager', DummyImager)
        self.cache = DashboardCache("http://example.com/selenium", {
            "dash1": "http://example.com/dash1",
            "dash2": "http://example.com/dash2",
            }, 5)

    def tearDown(self):
        self.cache.stop()

    @inlineCallbacks
    def test_refresh_images(self):
        yield self.cache._refresh_images()
        self.assertEqual(self.cache.pngs, {
            "dash1": "A dummy PNG.",
            "dash2": "A dummy PNG.",
            })

    @inlineCallbacks
    def test_get_png(self):
        yield self.cache._refresh_images()
        png = self.cache.get_png("dash1")
        self.assertEqual(png, "A dummy PNG.")

    def test_get_png_missing(self):
        png = self.cache.get_png("dash1")
        self.assertEqual(png, None)

    def test_start_and_stop(self):
        self.cache.start()
        self.assertTrue(self.cache.update_task.running)
        self.assertEqual(self.cache.update_task.f,
                         self.cache._refresh_images)
        self.assertEqual(self.cache.update_task.interval,
                         5)

        self.cache.stop()
        self.assertFalse(self.cache.update_task.running)

    @inlineCallbacks
    def test_failed_image(self):
        class FailedPng(Exception):
            pass

        def fail():
            raise FailedPng("No PNG. :(")

        self.cache.dashboards["dash1"].generate_png = fail
        yield self.cache._refresh_images()
        errors = self.flushLoggedErrors(FailedPng)
        self.assertEqual(len(errors), 1)
        self.assertEqual(self.cache.pngs, {
            "dash1": None,
            "dash2": "A dummy PNG.",
            })


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
