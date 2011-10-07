"""Server for sending metrics to Geckoboard."""

import json
import copy

from twisted.application.service import Service
from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.web import http
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue


class GeckoboardResourceBase(Resource):
    isLeaf = True

    def __init__(self, metrics_source):
        Resource.__init__(self)
        self.metrics_source = metrics_source

    @inlineCallbacks
    def do_render_GET(self, request):
        json_data = yield self.get_data(request)
        request.setResponseCode(http.OK)
        request.setHeader("content-type", "application/json")
        request.write(json.dumps(json_data))
        request.finish()

    def render_GET(self, request):
        self.do_render_GET(request)
        return NOT_DONE_YET

    def get_data(self, request):
        raise NotImplementedError("Sub-classes should implement get_data")


class GeckoboardLatestResource(GeckoboardResourceBase):

    @inlineCallbacks
    def get_data(self, request):
        metric_name = request.args['metric'][0]
        latest, prev = yield self.metrics_source.get_latest(metric_name)
        data = {"item": [
            {"text": "", "value": latest},
            {"text": "", "value": prev},
            ]}
        returnValue(data)


class GeckoboardHighchartResource(GeckoboardResourceBase):

    HIGHCHART_BASE = {
        'chart': {
            'renderTo': 'container',
            'plotBackgroundColor': None,
            'backgroundColor': None,
            },
        'credits': {'enabled': False},
        'title': {'text': None},
        'plotOptions': {
            'line': {
                'allowPointSelect': True,
                'cursor': 'pointer',
                },
            },
        'series': [],
        }

    SERIES_BASE = {
        'type': 'line',
        }

    @inlineCallbacks
    def get_data(self, request):
        metrics = request.args['metric']
        if 'minutes' in request.args:
            minutes = int(request.args['minutes'][0])
        else:
            minutes = 60  # default to 1hr
        data = copy.deepcopy(self.HIGHCHART_BASE)
        for metric in metrics:
            series = copy.deepcopy(self.SERIES_BASE)
            series['name'] = metric
            series['data'] = yield self.metrics_source.get_history(metric,
                                                                   minutes)
            data['series'].append(series)
        returnValue(data)


class GeckoboardResource(Resource):

    def __init__(self, metrics_source):
        Resource.__init__(self)
        self.putChild('latest', GeckoboardLatestResource(metrics_source))
        self.putChild('history', GeckoboardHighchartResource(metrics_source))


class GeckoServer(Service):
    def __init__(self, metrics_source, port):
        self.webserver = None
        self.port = port
        self.site_factory = Site(GeckoboardResource(metrics_source))

    @inlineCallbacks
    def startService(self):
        self.webserver = yield reactor.listenTCP(self.port,
                                                 self.site_factory)

    @inlineCallbacks
    def stopService(self):
        if self.webserver is not None:
            yield self.webserver.loseConnection()
