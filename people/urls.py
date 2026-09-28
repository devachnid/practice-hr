from django.http import HttpResponse
from django.urls import path

app_name = "people"
urlpatterns = [
    path("me/", lambda r: HttpResponse("me"), name="me"),
    path("team/", lambda r: HttpResponse("team"), name="team"),
]
