from django.urls import path

from . import views

app_name = "documents"
urlpatterns = [
    path("file/<int:pk>/", views.download, name="download"),
    path("policies/", views.policies_page, name="policies"),
    path("policies/passkey-options/", views.passkey_options, name="passkey_options"),
    path("policies/<int:pk>/sign/", views.sign, name="sign"),
]
