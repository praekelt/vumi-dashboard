# -*- test-case-name: vumidash.tests.test_gecko_server -*-

"""Server for sending metrics to Geckoboard."""

import json
import copy
from datetime import timedelta

from twisted.application.service import Service
from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.web import http
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue


def get_value(name, args, default):
    if name not in args:
        return default
    return args[name][0]


def parse_timedelta(name, args, default):
    value = get_value(name, args, default)
    for unit, key in [('d', 'days'), ('min', 'minutes'),
                      ('s', 'seconds')]:
        if value.endswith(unit):
            period = int(value[:-len(unit)])
            return timedelta(**{key: period})
    return timedelta(int(value))


def parse_float(name, args, default):
    value = get_value(name, args, default)
    return float(value) if value is not None else None


def parse_boolean(name, args, default):
    value = str(get_value(name, args, default)).lower()
    if value in ['0', 'false', 'no']:
        return False
    return True


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
        summary_size = parse_timedelta('step', request.args, '5min')
        latest, prev = yield self.metrics_source.get_latest(metric_name,
                                                            summary_size)
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
                'marker': {
                    'enabled': False,
                    },
                },
            },
        'series': [],
        'xAxis': {
            'type': 'datetime',
            },
        'yAxis': {},
        }

    SERIES_BASE = {
        'type': 'line',
        }

    @inlineCallbacks
    def get_data(self, request):
        metrics = request.args['metric']
        if 'label' in request.args:
            labels = request.args['label']
            assert len(labels) == len(metrics)
        else:
            labels = metrics
        from_dt = parse_timedelta('from', request.args, '-1d')
        until_dt = parse_timedelta('until', request.args, '-0s')
        step_dt = parse_timedelta('step', request.args, '5min')
        y_min = parse_float('ymin', request.args, None)
        show_markers = parse_boolean('markers', request.args, 'false')
        skip_nulls = parse_boolean('skip_nulls', request.args, 'true')
        data = copy.deepcopy(self.HIGHCHART_BASE)
        if y_min is not None:
            data['yAxis']['min'] = y_min
        data['plotOptions']['line']['marker']['enabled'] = show_markers
        for label, metric in zip(labels, metrics):
            series = copy.deepcopy(self.SERIES_BASE)
            series['name'] = label
            series['data'] = yield self.metrics_source.get_history(
                                        metric, from_dt, until_dt, step_dt,
                                        skip_nulls)
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
