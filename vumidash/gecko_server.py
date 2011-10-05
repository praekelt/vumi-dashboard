"""Server for sending metrics to Geckoboard."""

import json

from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.web import http


class GeckoboardResourceBase(Resource):
    isLeaf = True

    def __init__(self, metrics_source):
        self.metrics_source = metrics_source
        Resource.__init__(self)

    def render_GET(self, request):
        json_data = self.get_data(request)
        request.setResponseCode(http.OK)
        request.setHeader("content-type", "application/json")
        return json.dumps(json_data)

    def get_data(self, request):
        raise NotImplementedError("Sub-classes should implement get_data")


class GeckoboardLatestResource(GeckoboardResourceBase):

    def get_data(self, request):
        metric_name = request.path
        latest, prev = self.metrics_source.get_latest(metric_name)
        data = {"item": [
            {"text": "", "value": latest},
            {"text": "", "value": prev},
            ]}
        return data


class GeckoboardHighchartResource(GeckoboardResourceBase):

    HIGHCHART_BASE = {
        'chart': {},
        'colors': [
            '#058DC7',
            '#50B432',
            '#EF561A',
            ],
        'credits': {'enabled': False},
        'title': {'text': None},
        'plotOptions': {
            'line': {
                'allowPointSelect': True,
                'cursor': 'pointer',
                },
            },
        'series': [{
            'type': 'line',
            'name': '???',
            'data': [
                ['Free', 13491],
                ['Premium', 313],
                ]
            }],
        }

    def get_data(self, request):
        data = self.HIGHCHART_BASE.copy()
        return data


class GeckoServer(object):
    def __init__(self, metrics_source):
        self.metrics_source = metrics_source
