.. _generic:

Generic
#######

The generic API can be used for buyers and sellers.

.. _buyer-label:

Buyers
======

Buyers are identified by a UUID, which is a string (max 255 chars) that makes
sense to the client. It must be unique within solitude, so we'd recommend
prefixing the UUID, eg: ``marketplace:<your-uuid>``

*Note*: after `spartacus was merged <https://github.com/mozilla/spartacus/>`_
some of these fields and features were no longer needed but remain in service.

Create
------

Buyers are added to solitude by an HTTP `POST` call. The POST should contain
a unique UUID as well as the PIN the buyer has chosen:

.. http:post:: /generic/buyer/

    :<json string uuid: a unique identifier string.
    :<json bool active: True if this is an active account.
    :<json bool authenticated:
        True if this user account was authenticated in a trusted way.
        For example, if the email has been verified using the Firefox Accounts
        OAuth API then you would say this account has been authenticated.
    :<json string email: email address.
    :<json string locale:
        `ISO 639 <https://en.wikipedia.org/wiki/ISO_639>`_
        locale code to indicate the buyer's preferred locale.
        See the example below for how it looks.

    .. code-block:: json

        {
            "uuid": "93e33277-87f7-417b-8ed2-371672b5297e",
            "email": "someone@somewhere.org",
            "locale": "fr,en;q=0.7,en-US;q=0.3"
        }

    **Response**

    .. code-block:: json

        {
            "active": false,
            "counter": null,
            "email": "someone@somewhere.org",
            "locale": "fr,en;q=0.7,en-US;q=0.3",
            "needs_pin_reset": false,
            "new_pin": false,
            "pin": false,
            "pin_confirmed": false,
            "pin_failures": 0,
            "pin_is_locked_out": false,
            "pin_was_locked_out": false,
            "resource_pk": 4,
            "resource_uri": "/generic/buyer/4/",
            "uuid": "93e33277-87f7-417b-8ed2-371672b5297e"
        }

    :status 201: successfully processed.

List and retrieve
-----------------

List buyers:

.. http:get:: /generic/buyer/

    You can filter on the following parameters.

    :param active: the active flag for a user.
    :param email: users email address.
    :param uuid: the uuid for a user.

    **Response**

    A standard listing response containing buyers (see below).

Get the details of a buyer:

.. http:get:: /generic/buyer/int:id/

    **Response**

    .. code-block:: json

        {
            "active": false,
            "counter": null,
            "email": "",
            "locale": "fr,en;q=0.7,en-US;q=0.3",
            "needs_pin_reset": false,
            "new_pin": false,
            "pin": false,
            "pin_confirmed": false,
            "pin_failures": 0,
            "pin_is_locked_out": false,
            "pin_was_locked_out": false,
            "resource_pk": 4,
            "resource_uri": "/generic/buyer/4/",
            "uuid": "93e33277-87f7-417b-8ed2-371672b5297e"
        }

    :param email: users email address.
    :param type: string
    :param locale: users locale, most likely the Accept Language HTTP header
    :param type: string
    :param pin:
        in a POST a PIN is a string, but in responses, the PIN is never
        returned. It returns a boolean, `true` if a PIN is present, `false`
        if not.
    :param type: boolean
    :param pin_confirmed: if the pin has been confirmed.
    :param type: boolean
    :param new_pin: a `new_pin` so that a confirmation can be made.
    :param type: boolean
    :param active: if the buyer is currently active or not, defaults to `true`
    :param type: boolean
    :param pin_locked_out: if the PIN is currently locked out.
    :param type: boolean
    :param pin_failures:
        the number of failed PIN entries. Reset to 0 on successful entry.
        When a threshold is reached defined by `PIN_FAILURES` in settings.
    :param type: int

Confirm PIN
-----------

Once you have created a buyer with a PIN, you'll need to have the buyer confirm
their PIN. Once you've received their confirmed PIN you can POST to the
``confirm_pin`` endpoint like so:

.. http:post:: /generic/confirm_pin/

    **Request**

    .. code-block:: json

        {
            "uuid": "93e33277-87f7-417b-8ed2-371672b5297e",
            "pin": "8472"
        }

    **Response**

    .. code-block:: json

        {
            "confirmed": false,
            "uuid": "93e33277-87f7-417b-8ed2-371672b5297e"
        }

    :status 200: uuid found and PIN processed, check `confirmed` in the result
    :status 404: uuid not found.

    :param confirmed:
        if `true` the PIN matched, if `false` the PIN did not match.
    :type confirmed: boolean

Verify PIN
----------

Once you have a buyer with a confirmed pin, the next time they go to purchase
something you can simply verify their PIN using the ``verify_pin`` endpoint:

.. http:post:: /generic/verify_pin/

    **Request**

    .. code-block:: json

        {
            "pin": "1224",
            "uuid": "93e33277-87f7-417b-8ed2-371672b5297e"
        }

    **Response**

    .. code-block:: json

        {
            "locked": false,
            "pin": "1224",
            "uuid": "93e33277-87f7-417b-8ed2-371672b5297e",
            "valid": false
        }

Errors are handled much in the same way as ``confirm_pin``. Calling this
endpoint 5 times with the wrong PIN will lock the buyer. See `Locked State`_
for more information.

This change in state is the reason there is no `GET` endpoint for this API.

Reset
-----

To start the reset flow, set the ``needs_pin_reset`` attribute on the buyer by
patching the buyer:

.. http:patch:: /generic/buyer/int:id/

    **Request**

    .. code-block:: json

        {
            "needs_pin_reset": true
        }

    **Response**

    :status 202: response processed.
    :status 404: buyer not found.

Next you get the buyer's new pin and patch the buyer again:

.. http:patch:: /generic/buyer/int:id/

    **Request**

    .. code-block:: json

        {
            "new_pin": "8259"
        }

    **Response**

    :status 202: response processed.
    :status 404: buyer not found.

After these two steps you will use the ``reset_confirm_pin`` endpoint. It works
the same way as the ``confirm_pin`` endpoint but instead checks against the
buyer's ``new_pin`` rather than their ``pin``:

.. http:post::: /generic/reset_confirm_pin/

    **Request**

    .. code-block:: json

        {
            "uuid": "93e33277-87f7-417b-8ed2-371672b5297e",
            "pin": "8259"
        }

    **Response**

    .. code-block:: json

        {
            "confirmed": false,
            "uuid": "93e33277-87f7-417b-8ed2-371672b5297e"
        }


    :status 200: uuid found and PIN processed, check `confirmed` in the result
    :status 404: uuid not found.

Locked State
------------

A buyer becomes locked when there have been 5 failed attempts to verify the
PIN. Once the buyer is locked the verify PIN action will not be usable for 5
minutes. You can tell if a buyer is locked by checking the
``pin_is_locked_out`` property of the buyer data. Buyers that were locked out
since the last time the PIN was changed or successfully verified will have the
``pin_was_locked_out`` property set to ``true``.

Close
-----

This does not delete the buyer, but does the following:

* calls a close signal the payment providers can listen to, in the case of Braintree it cancels all payment methods and subscriptions
* sets the account to inactive
* removes the email
* sets the uuid to something anonymous

Note: only if the close signal is succesfully processed will the account be set to inactive.

.. http:post:: /generic/buyer/int:id/close/

    :status 204: account closed successfully
    :status 400: problem processing the uuid into a buyer
    :status 404: active buyer not found, will trigger if you try to close an account twice
    :status 500: something went wrong with closing the account

The account is not deleted and can still be accessed by the URL to that account to preserve data integrity. For example:

* create a buyer with a POST to `/generic/buyer`
* store the `resource_uri` in the response
* close the buyer with a POST to `/generic/buyer/int:id/close`
* get the buyer with a GET to `resource_uri`, a *truncated* version of the response shows:

  .. code-block:: json

    {
        "active": False,
        "email": "",
        "uuid": "anonymised-uuid:1b3db7a9-0e8f-43d8-b8da-b3317a147068"
    }



.. _seller-label:

Sellers
=======

Sellers are identified by a UUID, which is a string (max 255 chars) that makes
sense to the client. It must be unique within solitude, so we'd recommend
prefixing the UUID, eg: `marketplace:<your-uuid>`

Sellers are added to solitude by a `POST` call. The POST should contain a unique UUID:

.. http:post:: /generic/seller/

    .. code-block:: json

        {
            "uuid": "acb21517-df02-4734-8173-176ece310bc1"
        }

You can else get the details of a seller:

.. http:get:: /generic/seller/9/

    .. code-block:: json

        {
            "uuid": "acb21517-df02-4734-8173-176ece310bc1",
            "resource_uri": "/generic/seller/9/",
            "resource_pk": 16
        }

.. _seller-product:

Product
=======

A product is a generic product that is being sold. To create a product specific
payment provider, a generic product must first be created.

.. http:post:: /generic/product/

    Create a new product.

    .. code-block:: json

        {
            "access": 1,
            "external_id": "external:5864962b-033e-4c7f-aabb-a3cd262e7042",
            "public_id": "product:279ae330-1c33-459d-b6ba-c22e5cba1c48",
            "secret": "some-secret",
            "seller": "/generic/seller/3/"
        }

    * ``seller``: is a seller created with the :ref:`generic seller endpoint <seller-label>`.

    * ``external_id``: an id that corresponds to the sellers catalog.

    * ``public_id``: a publicly used id that will be used in the payment flow.

    * ``secret``: a generic back-end secret field, used for Paypal.

    * ``access``: either ``1`` seller will be used for purchasing or ``2``
      seller can only be used for simulating payments.

.. http:get:: /generic/product/id:int/

    Get an existing product.

    .. code-block:: json

        {
            "access": 1,
            "counter": "0",
            "created": "2015-02-05T12:41:50",
            "external_id": "external:5864962b-033e-4c7f-aabb-a3cd262e7042",
            "modified": "2015-02-05T12:41:50",
            "public_id": "product:279ae330-1c33-459d-b6ba-c22e5cba1c48",
            "resource_pk": 1,
            "resource_uri": "/generic/product/1/",
            "secret": "some-secret",
            "seller": "/generic/seller/3/",
            "seller_uuids": {
                "bango": null,
                "reference": null
            }
        }

    * ``seller_uuids``: is a mapping of uuids for the specific payment
      providers.

.. _transaction-label:

Transaction
===========

A transaction is created at the start of a payment through solitude. Its
status is altered as the transaction is completed or cancelled as appropriate.

To iterate over the list of transactions:

.. http:get:: /generic/transaction/

To get an individual transaction:

.. http:get:: /generic/transaction/id:int/

    .. code-block:: json

        {
            "amount": "0.62",
            "buyer": null,
            "created": "2013-04-15T05:39:22",
            "currency": "GBP",
            "notes": "",
            "pay_url": "https://provider.com/pay?transaction=1234",
            "provider": 1,
            "related": null,
            "relations": [],
            "resource_pk": 2977,
            "resource_uri": "/generic/transaction/2977/",
            "seller": "/generic/seller/385/",
            "seller_product": "/generic/product/449/",
            "status": 5,
            "type": 0,
            "uid_pay": "230450",
            "uid_support": "0",
            "uuid": "webpay:d8d143f3-d484-4903-bd29-bae3d280c5b3"
        }

Statuses:

* 0: ``Pending`` - when the transaction has started, the payment flow has been
  started and has been redirected on to the payment provider. For Bango, this
  is pretty much right away. This is the default.

* 1: ``Completed`` - the payment has been fully completed and processed.

* 2: ``Checked`` - the payment is in process and has been checked. This can be
  checked by a server to server notice (IPN for Paypal, Event Notification
  for Bango) or a manual transaction check. When checking to see if
  a transaction is successful, check to see if its ``Completed`` or
  ``Checked``.

* 3: ``Received`` - we have received the transaction, but have not acted on it
  yet. This is an intermediate step between starting the
  transaction and passing it on to the payment provider. Bango does not use
  this.

* 4: ``Failed`` - an error occurred and the transaction failed.

* 5: ``Cancelled`` - the transaction was cancelled explicitly by the user.

* 6: ``Started`` - the calling application (e.g. webpay) has started preparing
  this transaction.

* 7: ``Errored`` - the calling application (e.g. webpay) was unable to
  complete creating the transaction because of an error.

To create a new transaction:

.. http:post:: /generic/transaction/

    .. code-block:: json

        {
            "amount": "0.62",
            "buyer": null,
            "currency": "GBP",
            "notes": "",
            "pay_url": "https://provider.com/pay?transaction=1234",
            "provider": 1,
            "seller": "/generic/seller/385/",
            "seller_product": "/generic/product/449/",
            "source": "bango",
            "status": 5,
            "type": 0,
            "uid_pay": "230450",
            "uid_support": "0",
            "uuid": "webpay:d8d143f3-d484-4903-bd29-bae3d280c5b3"
        }


.. http:get:: /generic/transaction/id:int/

    Update an existing transaction.

    .. code-block:: json

        {
            "status_reason": "PROVIDER_LOOKUP_FAILURE"
        }

    **Note:** not all fields can updated all the time, the ability to update
    a transaction is based upon logic within the transaction.

    Only the following fields can be altered without limitation.

    * ``notes``

    * ``pay_url``

    * ``status_reason``

    * ``uid_pay``

    Fields that can altered with limitation:

    * ``provider``: can be set, only if it is not set.

    * ``status``: see status notes below.

    Status changes are limited in the following way:

    * if a transaction was created before ``settings.TRANSACTION_LOCKDOWN``
      then it cannot be altered.

    * if a transaction is ``Failed``, ``Cancelled`` or ``Errored`` its
      status cannot be altered.

    * if a transaction is in ``Checked`` or ``Received`` it can only be moved
      to ``Completed`` or ``Failed``.
