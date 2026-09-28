from django.urls import path

from absence.views import requests

app_name = "absence"
urlpatterns = [
    path("request/", requests.request_leave, name="request"),
    path("mine/", requests.mine, name="mine"),
    path("<int:pk>/cancel/", requests.cancel, name="cancel"),
    path("<int:pk>/kit-day/", requests.kit_day, name="kit_day"),
]
