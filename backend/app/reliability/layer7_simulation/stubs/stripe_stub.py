"""Stripe API stubs — charges, customers, subscriptions, webhooks."""
from __future__ import annotations

from app.reliability.layer7_simulation.wiremock_manager import StubMapping


def get_stubs() -> list[StubMapping]:
    return [
        # ── Charges ──────────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/charges",
            status=200,
            response_body={
                "id": "ch_mock_001",
                "object": "charge",
                "amount": 2000,
                "currency": "usd",
                "status": "succeeded",
                "paid": True,
            },
        ),
        # ── Customers ────────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/customers",
            status=200,
            response_body={
                "id": "cus_mock_001",
                "object": "customer",
                "email": "test@forge.dev",
                "created": 1700000000,
            },
        ),
        StubMapping(
            method="GET",
            path="/v1/customers/:id",
            status=200,
            response_body={
                "id": "cus_mock_001",
                "object": "customer",
                "email": "test@forge.dev",
            },
        ),
        # ── Subscriptions ────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/subscriptions",
            status=200,
            response_body={
                "id": "sub_mock_001",
                "object": "subscription",
                "status": "active",
                "current_period_start": 1700000000,
                "current_period_end": 1702592000,
            },
        ),
        StubMapping(
            method="GET",
            path="/v1/subscriptions/:id",
            status=200,
            response_body={
                "id": "sub_mock_001",
                "object": "subscription",
                "status": "active",
            },
        ),
        # ── Payment Intents ──────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/payment_intents",
            status=200,
            response_body={
                "id": "pi_mock_001",
                "object": "payment_intent",
                "status": "requires_payment_method",
                "client_secret": "pi_mock_001_secret_mock",
                "amount": 2000,
                "currency": "usd",
            },
        ),
        StubMapping(
            method="POST",
            path="/v1/payment_intents/:id/confirm",
            status=200,
            response_body={
                "id": "pi_mock_001",
                "object": "payment_intent",
                "status": "succeeded",
            },
        ),
        # ── Checkout Sessions ────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/checkout/sessions",
            status=200,
            response_body={
                "id": "cs_mock_001",
                "object": "checkout.session",
                "url": "https://checkout.stripe.com/mock",
                "status": "open",
            },
        ),
        # ── Webhook signature verification (always valid) ────────
        StubMapping(
            method="POST",
            path="/v1/webhooks",
            status=200,
            response_body={"received": True},
        ),
        # ── Products ─────────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/products",
            status=200,
            response_body={
                "id": "prod_mock_001",
                "object": "product",
                "name": "Mock Product",
                "active": True,
            },
        ),
        # ── Prices ───────────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/prices",
            status=200,
            response_body={
                "id": "price_mock_001",
                "object": "price",
                "unit_amount": 2000,
                "currency": "usd",
                "recurring": {"interval": "month"},
            },
        ),
    ]
