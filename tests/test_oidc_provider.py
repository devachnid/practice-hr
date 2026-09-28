from django.core.management import call_command
from oauth2_provider.models import Application

from accounts.oidc import Validator
from tests.factories import make_employee


def test_discovery_document(client):
    r = client.get("/o/.well-known/openid-configuration/")
    assert r.status_code == 200
    doc = r.json()
    assert "authorization_endpoint" in doc and "jwks_uri" in doc


def test_register_client_prints_credentials_once(db, capsys):
    call_command("register_oidc_client", name="rota", redirect_uri="https://rota.example/oidc/callback/")
    out = capsys.readouterr().out
    app = Application.objects.get(name="rota")
    assert app.client_id in out and "client_secret=" in out
    assert app.skip_authorization and app.algorithm == "RS256"
    assert app.client_type == Application.CLIENT_CONFIDENTIAL
    assert app.authorization_grant_type == Application.GRANT_AUTHORIZATION_CODE


def test_claims_carry_email_and_employee_id(employee_user):
    e = make_employee(user=employee_user)
    request = type("R", (), {"user": employee_user})()
    claims = Validator().get_additional_claims(request)
    assert claims == {"email": "sam@example.com", "employee_id": e.pk}


def test_claims_without_employee(employee_user):
    request = type("R", (), {"user": employee_user})()
    assert Validator().get_additional_claims(request) == {"email": "sam@example.com", "employee_id": None}
