"""Tests for vumidash.gecko_imager."""

import os
from xml.dom import minidom

from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor, threads
from twisted.web.client import getPage
from twisted.web import http
from twisted.web.server import Site
from twisted.web.resource import Resource

from vumidash import gecko_imager
from vumidash.gecko_imager import (DashboardImager, DashboardCache,
                                   GeckoImageServer)


class MockGeckoboardResource(Resource):
    isLeaf = True

    GECKO_HTML = """<html><body>
    <div id="dashboard-wrapper">
        <div class="b-widget loaded">Widget 1</div>
        <div class="b-widget loaded">Widget 2</div>
    </div>
    </html>
    """

    def render_GET(self, request):
        request.setResponseCode(http.OK)
        request.setHeader("content-type", "text/html")
        return self.GECKO_HTML


class TestDashboardImager(unittest.TestCase):

    @inlineCallbacks
    def setUp(self):
        remote = os.environ.get("VUMIDASH_SELENIUM_REMOTE")
        if remote is None:
            raise unittest.SkipTest("Define VUMIDASH_SELENIUM_REMOTE"
                                    " to run DashboardImager tests.")
        site = Site(MockGeckoboardResource())
        self.webserver = yield reactor.listenTCP(0, site)
        addr = self.webserver.getHost()
        url = "http://127.0.0.1:%s/" % addr.port
        self.imager = DashboardImager(remote, url)

    @inlineCallbacks
    def tearDown(self):
        if hasattr(self, "webserver"):
            yield self.webserver.loseConnection()

    @inlineCallbacks
    def test_generate_image(self):
        png = yield threads.deferToThread(self.imager.generate_png)
        open("test.png", "wb").write(png)
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

    @inlineCallbacks
    def test_start_and_stop(self):
        self.cache.start()
        self.assertTrue(self.cache.update_task.running)
        self.assertEqual(self.cache.update_task.f,
                         self.cache._refresh_images)
        self.assertEqual(self.cache.update_task.interval,
                         5)

        yield self.cache.stop()
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

    @inlineCallbacks
    def test_clear_cache(self):
        yield self.cache._refresh_images()
        self.cache.clear()
        self.assertEqual(self.cache.pngs, {
            "dash1": None,
            "dash2": None,
            })


class TestGeckoImageServer(unittest.TestCase):

    @inlineCallbacks
    def setUp(self):
        self.patch(gecko_imager, 'DashboardImager', DummyImager)
        self.web_path = "vumidashtest"
        dashboards = {
            "dash1": "http://example.com/dash1",
            }
        self.service = GeckoImageServer(self.web_path, 0,
                                        "http://example.com/selenium",
                                        dashboards, 30)
        yield self.service.startService()
        # stop dashboard cache to give explicit control during tests
        yield self.service.dashboard_cache.stop()
        self.service.dashboard_cache.clear()
        addr = self.service.webserver.getHost()
        self.url = "http://%s:%s/" % (addr.host, addr.port)

    @inlineCallbacks
    def tearDown(self):
        yield self.service.stopService()

    @inlineCallbacks
    def get_route(self, route, errback=None):
        d = getPage(self.url + self.web_path + route, timeout=1)
        if errback:
            d.addErrback(errback)
        data = yield d
        returnValue(data)

    @inlineCallbacks
    def test_dashboard(self):
        yield self.service.dashboard_cache._refresh_images()
        result = yield self.get_route("/png/dash1")
        self.assertEqual(result, "A dummy PNG.")

    @inlineCallbacks
    def test_uncached_dashboard(self):
        errors = []
        yield self.get_route("/png/dash1", errback=errors.append)
        [error] = errors
        self.assertEqual(error.getErrorMessage(), "503 Dashboard not loaded.")

    @inlineCallbacks
    def test_unknown_dashboard(self):
        errors = []
        yield self.get_route("/png/unknown1", errback=errors.append)
        [error] = errors
        self.assertEqual(error.getErrorMessage(), "404 Dashboard not found.")

    @inlineCallbacks
    def test_dashboard_list(self):
        result = yield self.get_route("")
        doc = minidom.parseString(result)
        [title] = doc.getElementsByTagName('title')
        self.assertEqual(title.childNodes[0].wholeText,
                         u'Vumidash Dashboard Cache')
        links = [elem.attributes['href'].value
                 for elem in doc.getElementsByTagName('a')]
        self.assertEqual(links, [
            "/vumidashtest/png/dash1",
            ])

    @inlineCallbacks
    def test_health_resource(self):
        result = yield getPage(self.url + "health", timeout=1)
        self.assertEqual(result, "OK")
