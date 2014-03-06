import urlparse

from django import http
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse

import requests
from curling.lib import sign_request
from django_statsd.clients import statsd
from lxml import etree
from slumber import url_join

from lib.bango.constants import HEADERS_SERVICE_GET

from lib.paypal.client import get_client as paypal_client
from lib.paypal.constants import HEADERS_URL_GET, HEADERS_TOKEN_GET
from lib.paypal.map import urls

from solitude.logger import getLogger

log = getLogger('s.proxy')
bango_timeout = getattr(settings, 'BANGO_TIMEOUT', 10)


class Proxy(object):
    # Override this in your proxy class.
    name = None
    # Values that we'll populate from the request, optionally.
    body = None
    headers = None
    url = None
    # Name of settings variables.
    setting_proxy = 'SOLITUDE_PROXY'
    setting_timeout = ''
    # Nice name for the URL we are going to hit.
    service = ''

    def __init__(self):
        self.enabled = getattr(settings, self.setting_proxy, False)
        self.timeout = getattr(settings, self.setting_timeout, 10)

    def pre(self, request):
        """Do any processing of the incoming request."""
        self.method = request.META['REQUEST_METHOD'].lower()
        self.body = str(request.raw_post_data)
        try:
            self.service = request.META[HEADERS_URL_GET]
        except KeyError:
            log.error('Missing header: %s',
                      ', '.join(sorted(request.META.keys())))
            raise
        self.url = urls[self.service]

    def call(self):
        """Call the proxied service, return a response."""
        response = http.HttpResponse()
        method = getattr(requests, self.method)
        try:
            with statsd.timer('solitude.proxy.%s.%s' %
                              (self.service, self.name)):
                log.info('Calling service: %s at %s with %s' %
                         (self.service, self.url, self.method))
                # We aren't calling client._call because that tries to parse
                # the output. Once the headers are prepared, this will do the
                # rest.
                result = method(self.url, data=self.body,
                                headers=self.headers,
                                timeout=self.timeout, verify=True)
        except requests.exceptions.RequestException as err:
            log.exception('%s: %s' % (err.__class__.__name__, err))
            response.status_code = 500
            return response

        if result.status_code < 200 or result.status_code > 299:
            log.error('Warning response status: %s' % result.status_code)

        # Ensure the response passed along is updated with the response given.
        response.status_code = result.status_code
        response.content = result.text
        response['Content-Type'] = result.headers['Content-Type']
        return response

    def __call__(self, request):
        """Takes the incoming request and returns a response."""
        if not self.enabled:
            return http.HttpResponseNotFound()

        self.pre(request)
        response = self.call()
        response = self.post(response)
        return response

    def post(self, response):
        """Any post processing of the response here. Return the response."""
        return response


class PaypalProxy(Proxy):
    name = 'paypal'
    setting_timeout = 'PAYPAL_TIMEOUT'

    def pre(self, request):
        """
        Paypal does auth be special headers, so we'll need to process
        those and add those to the request.
        """
        super(PaypalProxy, self).pre(request)
        token = request.META.get(HEADERS_TOKEN_GET)
        if token:
            token = dict(urlparse.parse_qsl(token))

        client = paypal_client()
        self.headers = client.headers(self.url, auth_token=token)
        # Paypal requirs POST on its methods.
        self.method = 'post'


class BangoProxy(Proxy):
    name = 'bango'
    namespaces = ['com.bango.webservices.billingconfiguration',
                  'com.bango.webservices.directbilling',
                  'com.bango.webservices.mozillaexporter']
    setting_timeout = 'BANGO_TIMEOUT'
    service = 'bango'

    def __init__(self):
        self.enabled = getattr(settings, 'SOLITUDE_PROXY', False)
        self.timeout = getattr(settings, 'BANGO_TIMEOUT', 10)

    def tags(self, name):
        return ['{%s}%s' % (n, name) for n in self.namespaces]

    def pre(self, request):
        self.url = request.META[HEADERS_SERVICE_GET]
        self.headers = {'Content-Type': 'text/xml; charset=utf-8'}
        # All the Bango methods are a POST.
        self.method = 'post'

        # Alter the XML to include the username and password from the config.
        # Perhaps this can be done quicker with XPath.
        root = etree.fromstring(request.raw_post_data)
        #log.info(request.raw_post_data)
        username = self.tags('username')
        password = self.tags('password')
        changed_username = False
        changed_password = False
        for element in root.iter():
            if element.tag in username:
                element.text = settings.BANGO_AUTH.get('USER', '')
                changed_username = True
            elif element.tag in password:
                element.text = settings.BANGO_AUTH.get('PASSWORD', '')
                changed_password = True
            if changed_username and changed_password:
                break

        if not changed_username and not changed_password:
            log.info('Did not set a username and password on the request.')

        self.body = etree.tostring(root)


class ProviderProxy(Proxy):
    name = 'provider'

    def __init__(self, reference_name):
        self.reference_name = reference_name
        super(ProviderProxy, self).__init__()

    def pre(self, request):
        config = settings.ZIPPY_CONFIGURATION.get(self.reference_name)
        if not config:
            raise ImproperlyConfigured('No config: %s' % self.reference_name)

        # Headers we want from the proxying request.
        self.headers = {
            'Content-Type': request.META.get('CONTENT_TYPE'),
            'Accept': request.META.get('HTTP_ACCEPT')
        }
        self.body = str(request.raw_post_data)
        self.method = request.META['REQUEST_METHOD'].lower()
        # The URL is made up of the defined scheme and host plus the trailing
        # URL after the proxy in urls.py.
        root = len(reverse('provider.proxy',
                   kwargs={'reference_name':self.reference_name}))

        self.url = url_join(config['url'], request.META['PATH_INFO'][root:])
        # Add in the query string.
        query = request.META.get('QUERY_STRING')
        if query:
            self.url = '%s?%s' % (self.url, query)
        # Before we do the request, use curling to sign the request headers.
        sign_request(None, config['auth'], headers=self.headers,
                     method=self.method.upper(),
                     params={'oauth_token': 'not-implemented'},
                     url=self.url)


def provider(request, reference_name):
    return ProviderProxy(reference_name)(request)


def paypal(request):
    return PaypalProxy()(request)


def bango(request):
    return BangoProxy()(request)
