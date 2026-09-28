from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from oauth2_provider import views as oauth2_views
from oauth2_provider.urls import oidc_urlpatterns

from config.views import home

# The provider's endpoints, and nothing else django-oauth-toolkit ships.
# Its full urls.py also mounts application management (any signed-in person
# could register a client of their own at /o/applications/register/),
# authorized-token views, introspection, device flow, dynamic client
# registration and metadata. Clients are registered only by
# register_oidc_client, on the server; nobody registers one over the web.
# oidc_urlpatterns is discovery, the JWKS, userinfo and RP-initiated logout.
oauth2_urlpatterns = [
    path("authorize/", oauth2_views.AuthorizationView.as_view(), name="authorize"),
    path("token/", oauth2_views.TokenView.as_view(), name="token"),
    path("revoke_token/", oauth2_views.RevokeTokenView.as_view(), name="revoke-token"),
    *oidc_urlpatterns,
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("people/", include("people.urls")),
    path("", home, name="home"),
]

if settings.OAUTH2_PROVIDER["OIDC_ENABLED"]:
    urlpatterns.insert(
        1, path("o/", include((oauth2_urlpatterns, "oauth2_provider"), namespace="oauth2_provider")))
