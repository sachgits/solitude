from datetime import datetime

from django.core.urlresolvers import reverse

from braintree.payment_method import PaymentMethod
from braintree.payment_method_gateway import PaymentMethodGateway
from braintree.successful_result import SuccessfulResult
from nose.tools import eq_, ok_

from lib.brains.models import BraintreePaymentMethod
from lib.brains.tests.base import (
    BraintreeTest, create_braintree_buyer, create_method, error)
from solitude.constants import PAYMENT_METHOD_CARD, PAYMENT_METHOD_OPERATOR


def method(**kw):
    method = {
        'card_type': 'visa',
        'created_at': datetime.now(),
        'last_4': '7890',
        'token': 'da-token',
        'updated_at': datetime.now(),
    }
    method.update(**kw)
    return PaymentMethod(None, method)


def successful_method(**kw):
    return SuccessfulResult({'payment_method': method(**kw)})


class TestPaymentMethod(BraintreeTest):
    gateways = {'method': PaymentMethodGateway}

    def setUp(self):
        super(TestPaymentMethod, self).setUp()
        self.url = reverse('braintree:paymethod')

    def test_allowed(self):
        self.allowed_verbs(self.url, ['post'])

    def test_ok(self):
        self.mocks['method'].create.return_value = successful_method()

        buyer, braintree_buyer = create_braintree_buyer()
        res = self.client.post(self.url,
                               data={'buyer_uuid': buyer.uuid, 'nonce': '123'}
                               )
        data = {
            'customer_id': 'sample:id',
            'options': {'verify_card': True},
            'payment_method_nonce': u'123'
        }
        self.mocks['method'].create.assert_called_with(data)

        eq_(res.status_code, 201)
        eq_(res.json['braintree']['token'], 'da-token')

        method = BraintreePaymentMethod.objects.get()
        eq_(method.type_name, 'visa')

    def test_no_buyer(self):
        res = self.client.post(self.url,
                               data={'buyer_uuid': 'nope', 'nonce': '123'})
        eq_(res.status_code, 422)
        eq_(self.mozilla_error(res.json, 'buyer_uuid'), ['does_not_exist'])

    def test_no_buyerbraintree(self):
        buyer, braintree_buyer = create_braintree_buyer()
        braintree_buyer.delete()

        res = self.client.post(self.url,
                               data={'buyer_uuid': buyer.uuid, 'nonce': '123'})
        eq_(res.status_code, 422, res.content)
        eq_(self.mozilla_error(res.json, 'buyer_uuid'), ['does_not_exist'])

    def test_reached_max(self):
        self.mocks['method'].create.return_value = successful_method()
        buyer, braintree_buyer = create_braintree_buyer()
        res = self.client.post(
            self.url, data={'buyer_uuid': buyer.uuid, 'nonce': '123'})
        eq_(res.status_code, 201, res.content)

        with self.settings(BRAINTREE_MAX_METHODS=1):
            res = self.client.post(
                self.url, data={'buyer_uuid': buyer.uuid, 'nonce': '1234'})
            eq_(res.status_code, 422, res.content)
            eq_(self.mozilla_error(res.json, 'buyer_uuid'), ['max_size'])

    def test_braintree_fails(self):
        self.mocks['method'].create.return_value = error([{
            'attribute': 'payment_method_nonce',
            'message': 'Payment method nonce is invalid.',
            'code': '91925'
        }])

        buyer, braintree_buyer = create_braintree_buyer()
        res = self.client.post(self.url,
                               data={'buyer_uuid': buyer.uuid, 'nonce': '123'})
        ok_(not BraintreePaymentMethod.objects.exists())
        eq_(res.status_code, 422)
        eq_(self.braintree_error(res.json, 'payment_method_nonce'), ['91925'])


class TestDeletePaymentMethod(BraintreeTest):
    gateways = {'method': PaymentMethodGateway}

    def setUp(self):
        super(TestDeletePaymentMethod, self).setUp()
        self.url = reverse('braintree:paymethod.delete')

    def test_allowed(self):
        self.allowed_verbs(self.url, ['post'])

    def create_paymethod(self):
        buyer, braintree_buyer = create_braintree_buyer()
        return create_method(braintree_buyer)

    def post(self, obj, **kw):
        data = {'paymethod': obj.get_uri()}
        data.update(**kw)
        return self.client.post(self.url, data=data)

    def test_post(self):
        self.mocks['method'].delete.return_value = successful_method()

        obj = self.create_paymethod()
        res = self.post(obj)
        eq_(res.status_code, 204, res.status_code)

        self.mocks['method'].delete.assert_called_with(obj.provider_id)

    def test_braintree_delete_failure(self):
        self.mocks['method'].delete.return_value = error()

        obj = self.create_paymethod()
        res = self.post(obj)
        eq_(res.status_code, 422, res.content)
        eq_(obj.reget().active, True)

        self.mocks['method'].delete.assert_called_with(obj.provider_id)

    def test_cannot_delete_inactive_paymethod(self):
        obj = self.create_paymethod()
        obj.active = False
        obj.save()

        res = self.post(obj)
        eq_(res.status_code, 422, res.content)


class TestBraintreeBuyerMethod(BraintreeTest):

    def setUp(self):
        self.buyer, self.braintree_buyer = create_braintree_buyer()
        self.url = reverse('braintree:mozilla:paymethod-list')
        super(TestBraintreeBuyerMethod, self).setUp()

    def test_allowed(self):
        self.allowed_verbs(self.url, ['get'])

    def create(self):
        return BraintreePaymentMethod.objects.create(
            braintree_buyer=self.braintree_buyer,
            provider_id='some:id',
            truncated_id='some',
            type=PAYMENT_METHOD_CARD,
            type_name='visa')

    def test_get(self):
        obj = self.create()
        eq_(self.client.get(obj.get_uri()).json['resource_pk'], obj.pk)

    def test_patch(self):
        obj = self.create()
        res = self.client.patch(obj.get_uri(), data={'active': False})
        eq_(res.status_code, 200, res.content)
        eq_(self.client.get(obj.get_uri()).json['active'], False)

    def test_patch_read_only(self):
        obj = self.create()
        data = {
            'provider_id': 'different:id',
            'truncated_id': 'other',
            'type': PAYMENT_METHOD_OPERATOR,
            'type_name': 'mastercard'
        }
        res = self.client.patch(obj.get_uri(), data=data)
        eq_(res.status_code, 200)
        res = self.client.get(obj.get_uri())
        eq_(res.json['provider_id'], 'some:id')
        eq_(res.json['truncated_id'], 'some')
        eq_(res.json['type'], PAYMENT_METHOD_CARD)
        eq_(res.json['type_name'], 'visa')

    def test_list(self):
        # This is just a sanity check that the StrictQueryFilter is being
        # applied to queries. It is tested independently elsewhere.
        res = self.client.get(self.url, {'foo': 'bar'})
        eq_(res.status_code, 400, res.json)
