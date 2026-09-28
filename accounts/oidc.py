"""What the ID token and userinfo say about a person: their email and
their employee id. Nothing else leaves this system through sign-in."""

from oauth2_provider.oauth2_validators import OAuth2Validator


class Validator(OAuth2Validator):
    oidc_claim_scope = None  # every claim below is returned for the openid scope

    def get_additional_claims(self, request):
        user = request.user
        employee = getattr(user, "employee", None)
        return {"email": user.email, "employee_id": employee.pk if employee else None}
