from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from config.views import home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("people/", include("people.urls")),
    path("", home, name="home"),
]

if settings.OAUTH2_PROVIDER["OIDC_ENABLED"]:
    urlpatterns.insert(
        1, path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")))
