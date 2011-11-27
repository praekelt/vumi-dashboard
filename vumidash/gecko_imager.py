# -*- test-case-name: vumidash.tests.test_gecko_imager -*-

"""HTTP server that serves images generated from Geckoboard dashboards.

   This is useful for supporting browsers not supported by Geckoboard
   and possibly other things not yet imagined.

   The images are generated by using Selenium to script Firefox.
   """

import base64
import pkg_resources

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

from twisted.application.service import Service
from twisted.web import http
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor, threads
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall
from twisted.python import log


class DashboardImager(object):
    """Utility class for generating images.

    :type remote: str
    :param remote:
        URL of the selenium server.
    :type url: str
    :param url:
        URL of the dashboard
    """

    def __init__(self, remote, url):
        self.remote = remote
        self.url = url

    def _page_ready(self, driver):
        """Check that all the widgets are loaded."""
        wrapper = driver.find_element_by_id("dashboard-wrapper")
        loaded = True
        for widget in wrapper.find_elements_by_class_name("b-widget"):
            if "loaded" not in widget.get_attribute("class").split():
                loaded = False
                break
        return loaded

    def generate_png(self):
        """Return a binary string containing a PNG of the page."""
        driver = webdriver.Remote(self.remote,
                                  webdriver.DesiredCapabilities.FIREFOX)
        try:
            driver.get(self.url)
            WebDriverWait(driver, 10).until(self._page_ready)
            encoded_png = driver.get_screenshot_as_base64()
            png = base64.decodestring(encoded_png)
        finally:
            driver.quit()

        return png


class DashboardCache(object):
    """Caches and updates a set of dashboards."""

    def __init__(self, remote, dashboards, update_interval):
        self.update_interval = update_interval
        self.dashboards = {}
        self.pngs = {}
        for name, url in dashboards.items():
            self.dashboards[name] = DashboardImager(remote, url)
            self.pngs[name] = None
        self.update_task = LoopingCall(self._refresh_images)
        self.update_task_done = None

    @inlineCallbacks
    def _refresh_images(self):
        for name, imager in self.dashboards.items():
            d = threads.deferToThread(imager.generate_png)
            d.addErrback(lambda failure: log.err(failure))
            log.msg("Generating image for %s (%s)" % (name, imager.url))
            png = yield d
            if png is not None:
                self.pngs[name] = png

    def clear(self):
        for name in self.dashboards:
            self.pngs[name] = None

    def get_png(self, name):
        return self.pngs.get(name)

    def start(self):
        self.update_task_done = self.update_task.start(self.update_interval)

    def stop(self):
        if self.update_task.running:
            self.update_task.stop()
            return self.update_task_done


class DashboardPngResource(Resource):
    isLeaf = True

    def __init__(self, dashboard_cache):
        Resource.__init__(self)
        self.dashboard_cache = dashboard_cache

    def render_GET(self, request):
        dashboard = ".".join(request.postpath)
        if dashboard not in self.dashboard_cache.pngs:
            request.setResponseCode(http.NOT_FOUND, "Dashboard not found.")
            request.setHeader("Content-Type", "text/plain")
            return "Dashboard %r not found" % (dashboard,)
        png = self.dashboard_cache.get_png(dashboard)
        if png is None:
            request.setResponseCode(http.SERVICE_UNAVAILABLE, "Dashboard not"
                                    " loaded.")
            request.setHeader("Content-Type", "text/plain")
            return ("Dashboard %r not loaded. Please try again shortly."
                    % (dashboard,))
        request.setResponseCode(http.OK)
        request.setHeader("Content-Type", "image/png")
        return png


class DashboardResource(Resource):

    HTML_TEMPLATE = pkg_resources.resource_string(
        __name__, "dashboard_list_template.html")

    LINK_TEMPLATE = ('<li><a href="png/%(dashboard)s">%(dashboard)s</a></li>')

    def __init__(self, dashboard_cache):
        Resource.__init__(self)
        self.dashboard_cache = dashboard_cache
        self.putChild('png', DashboardPngResource(dashboard_cache))

    def get_links(self):
        links = []
        for name in self.dashboard_cache.dashboards:
            links.append(self.LINK_TEMPLATE % {"dashboard": name})
        return links

    def render_GET(self, request):
        context = {
            'links': "\n".join(self.get_links()),
            }
        request.setResponseCode(http.OK)
        request.setHeader("content-type", "text/html")
        return self.HTML_TEMPLATE % context


class HealthResource(Resource):
    isLeaf = True

    def render_GET(self, request):
        request.setResponseCode(http.OK)
        request.setHeader("content-type", "text/plain")
        return "OK"


class ImageServerResource(Resource):

    def __init__(self, web_path, dashboard_cache):
        Resource.__init__(self)
        self.putChild('health', HealthResource())
        self.putChild(web_path, DashboardResource(dashboard_cache))


class GeckoImageServer(Service):
    """Service that manages an HTTP server that serves static PNGs of
    Geckoboard dashboards.

    :type web_path: str
    :param web_path:
        Root path for web service.
    :type port: int
    :param port:
        Port for the HTTP server to listen on.
    :type selenium_remote: str
    :param selenium_remote:
        URL of the Selenium server to use.
    :type dashboard: dict
    :param dashboard:
        Mapping from dashboard names to dashboard URLs.
    :type update_interval: float
    :param update_interval:
        Number of seconds between dashboard image updates.
        Rendering dashboards takes on the order of tens of seconds
        so 30s * number of dashboards is a sensible minimum.
    """

    def __init__(self, web_path, port, selenium_remote, dashboards,
                 update_interval):
        self.webserver = None
        self.port = port
        self.dashboard_cache = DashboardCache(selenium_remote, dashboards,
                                              update_interval)
        self.site_factory = Site(ImageServerResource(web_path,
                                                     self.dashboard_cache))

    @inlineCallbacks
    def startService(self):
        self.dashboard_cache.start()
        self.webserver = yield reactor.listenTCP(self.port,
                                                 self.site_factory)

    @inlineCallbacks
    def stopService(self):
        yield self.dashboard_cache.stop()
        if self.webserver is not None:
            yield self.webserver.loseConnection()
