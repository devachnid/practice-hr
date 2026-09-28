"""Signed-in pages are not kept by the browser, and signing out clears what
it kept (config/middleware.py) — for the shared practice PC, where the next
person presses Back."""

import pytest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("url", ["/people/me/", "/accounts/account/"])
def test_signed_in_pages_are_not_stored(employee_client, url):
    resp = employee_client.get(url)
    assert resp.status_code == 200
    policy = resp["Cache-Control"]
    assert "no-store" in policy and "private" in policy


def test_the_admin_is_not_stored_either(admin_client):
    policy = admin_client.get("/admin/people/employee/")["Cache-Control"]
    assert "no-store" in policy and "private" in policy


def test_a_view_that_sets_its_own_policy_keeps_it(employee_client):
    """The provider's public keys are meant to be cached by relying
    parties, signed in or not."""
    assert employee_client.get("/o/.well-known/jwks.json")["Cache-Control"].startswith("public")


def test_signing_out_clears_the_browsers_copy(employee_client):
    resp = employee_client.post("/accounts/logout/")
    assert resp["Clear-Site-Data"] == '"cache"'


def test_signing_out_of_the_admin_does_too(admin_client):
    resp = admin_client.post("/admin/logout/")
    assert resp["Clear-Site-Data"] == '"cache"'


def test_anonymous_requests_are_left_alone(client):
    resp = client.get("/accounts/password_reset/done/")
    assert resp.status_code == 200
    assert "Clear-Site-Data" not in resp
    assert "no-store" not in resp.get("Cache-Control", "")
