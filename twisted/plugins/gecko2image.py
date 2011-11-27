import sys

from zope.interface import implements
import yaml

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker

from vumidash.gecko_imager import GeckoImageServer


class Options(usage.Options):
    optFlags = [
        ["config-help", None, "Print out help on the YAML configuration file"
                              " and exit"],
        ]

    optParameters = [
        ["config", "c", None, "The YAML configuration file"],
        ]

    def opt_config_help(self):
        print GeckoImageServer.__doc__
        print "See above for YAML configuration file parameters."
        sys.exit(0)


class Gecko2ImageServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "gecko2image"
    description = "Serve Geckoboard dashboards as static images"
    options = Options

    def makeService(self, options):
        config_file = options.pop("config")
        if not config_file:
            raise ValueError("please specify --config")

        with file(config_file, 'r') as stream:
            config = yaml.load(stream)

        web_path = config["web_path"]
        port = config["port"]
        selenium_remote = config["selenium_remote"]
        dashboards = config["dashboards"]
        update_interval = config["update_interval"]

        gecko_imager = GeckoImageServer(web_path, port, selenium_remote,
                                        dashboards, update_interval)
        return gecko_imager


# service maker instance for twistd

gecko2image = Gecko2ImageServiceMaker()
