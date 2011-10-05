from zope.interface import implements

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker

from vumidash.graphite_client import GraphiteClient
from vumidash.gecko_server import GeckoServer


class Options(usage.Options):
    optParameters = [
        ["graphite-url", "g", None, "The URL of the Graphite web service."],
        ["port", "p", 1235, "The port number to serve JSON to Geckoboard on."],
        ]


class Graphite2GeckoServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "graphite2gecko"
    description = "Read data from Graphite and serve it to Geckoboard"
    options = Options

    def makeService(self, options):
        """
        Construct a TCPServer from a factory defined in myproject.
        """
        graphite_url = options["graphite-url"]
        port = int(options["port"])
        metrics_source = GraphiteClient(graphite_url)
        gecko_server = GeckoServer(metrics_source, port)
        return gecko_server


# service maker instance for twistd

graphite2gecko = Graphite2GeckoServiceMaker()
