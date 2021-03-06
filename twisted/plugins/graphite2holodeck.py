from zope.interface import implements

import yaml

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker

from vumidash.graphite_client import GraphiteClient
from vumidash.dummy_client import DummyClient

# NOTE: We avoid importing vumidash.holodeck_pusher at the module level so
#       that twistd can import this module even when selenium isn't available.


class Options(usage.Options):
    optFlags = [
        ["dummy", None, "Use a dummy metrics source instead of reading"
                        " from Graphite."],
    ]

    optParameters = [
        ["graphite-url", "g", None, "The URL of the Graphite web service."],
        ["config", "c", None, "The YAML config file describing which metrics"
         " to push."],
    ]


class Graphite2HolodeckServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "graphite2holodeck"
    description = "Read data from Graphite and push it to Holodeck"
    options = Options

    def makeService(self, options):
        from vumidash.holodeck_pusher import HolodeckPusherService

        graphite_url = options["graphite-url"]
        with open(options["config"]) as f:
            config = yaml.safe_load(f.read())
        if options["dummy"]:
            metrics_source = DummyClient()
        else:
            metrics_source = GraphiteClient(graphite_url)
        holodeck_pusher = HolodeckPusherService(metrics_source, config)
        return holodeck_pusher


# service maker instance for twistd

graphite2holodeck = Graphite2HolodeckServiceMaker()
