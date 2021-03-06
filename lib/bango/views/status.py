import uuid

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse

from rest_framework.exceptions import ParseError
from rest_framework.mixins import CreateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ViewSet

from lib.bango.constants import STATUS_BAD, STATUS_GOOD
from lib.bango.errors import BangoImmediateError
from lib.bango.forms import CreateBillingConfigurationForm
from lib.bango.models import Status
from lib.bango.serializers import SellerProductBangoOnly, StatusSerializer
from lib.bango.views.base import BangoResource
from lib.bango.views.billing import prepare
from lib.transactions.constants import PROVIDER_BANGO
from solitude.base import ListModelMixin, RetrieveModelMixin
from solitude.constants import PAYMENT_METHOD_ALL
from solitude.logger import getLogger

log = getLogger('s.bango')


class StatusViewSet(CreateModelMixin, ListModelMixin,
                    RetrieveModelMixin, GenericViewSet):
    queryset = Status.objects.filter()
    serializer_class = StatusSerializer

    def post_save(self, obj, created):
        if created:
            log.info('Checking with bango: {0}'
                     .format(obj.seller_product_bango.pk))
            self.check_bango(obj)

    def check_bango(self, obj):
        view = BangoResource()
        pk = obj.seller_product_bango.pk
        form = CreateBillingConfigurationForm({
            'seller_product_bango': (
                self.get_serializer().fields['seller_product_bango']
                    .to_native(obj.seller_product_bango)),
            'pageTitle': 'Test of app status',
            'prices': [{'price': 0.99, 'currency': 'USD',
                        'method': PAYMENT_METHOD_ALL}],
            'redirect_url_onerror': 'http://test.mozilla.com/error',
            'redirect_url_onsuccess': 'http://test.mozilla.com/success',
            'transaction_uuid': 'test:status:{0}'.format(uuid.uuid4()),
            'user_uuid': 'test:user:{0}'.format(uuid.uuid4())
        })

        if not form.is_valid():
            log.info('Form not valid: {0}'.format(pk))
            raise ParseError

        try:
            data = prepare(form, obj.seller_product_bango.bango_id)
            view.client('CreateBillingConfiguration', data)
        except BangoImmediateError:
            # Cause the information about this record to be saved
            # by not raising an error.
            log.info('Bango error in check status: {0}'.format(pk))
            obj.status = STATUS_BAD
            obj.save()
            return

        log.info('All good: {0}'.format(pk))
        obj.status = STATUS_GOOD
        obj.save()


class DebugViewSet(ViewSet):

    def list(self, request):
        serializer = SellerProductBangoOnly(data=request.DATA)
        if serializer.is_valid():
            obj = serializer.object['seller_product_bango']
            result = {
                'bango': {
                    'environment': settings.BANGO_ENV,
                    'bango_id': obj.bango_id,
                    'package_id': obj.seller_bango.package_id,
                    'last_status': {},
                    'last_transaction': {}
                },
                'solitude': {
                }
            }

            # Show the last status check if present.
            try:
                latest = obj.status.latest()
                result['bango']['last_status'] = {
                    'status': latest.status,
                    'url': reverse('bango:status-detail',
                                   kwargs={'pk': latest.pk})
                }
            except ObjectDoesNotExist:
                pass

            # Show the last transaction if present.
            try:
                latest = (obj.seller_product.transaction_set.filter(
                    provider=PROVIDER_BANGO).latest())
                result['bango']['last_transaction'] = {
                    'status': latest.status,
                    'url': reverse('generic:transaction-detail',
                                   kwargs={'pk': latest.pk})
                }
            except ObjectDoesNotExist:
                pass

            return Response(result, status=200)

        return Response(serializer.errors, status=400)
