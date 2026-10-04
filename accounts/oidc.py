"""What the ID token and userinfo say about a person: their email, their
employee id, and whether they are an admin of the app asking (`admin`,
from their AppRole for that client; False with none). Nothing else leaves
this system through sign-in."""

from oauth2_provider.oauth2_validators import OAuth2Validator

from .models import AppRole


class Validator(OAuth2Validator):
    oidc_claim_scope = None  # every claim below is returned for the openid scope

    def validate_refresh_token(self, refresh_token, client, request, *args, **kwargs):
        """A refresh token outlives the ten-minute access and ID tokens, so a
        login made inactive (by an HR admin, or by hr_nightly for a leaver)
        must stop it working, as it stops every other way in."""
        if not super().validate_refresh_token(refresh_token, client, request, *args, **kwargs):
            return False
        return bool(request.user and request.user.is_active)

    def get_additional_claims(self, request):
        # request.client is the Application the token is for: set by client
        # authentication at the token endpoint (the ID token), and from the
        # access token's application at the userinfo endpoint.
        user = request.user
        employee = getattr(user, "employee", None)
        admin = AppRole.objects.filter(user=user, application=request.client, is_admin=True).exists()
        return {"email": user.email, "employee_id": employee.pk if employee else None, "admin": admin}
