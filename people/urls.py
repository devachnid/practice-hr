from django.urls import path

from . import views

app_name = "people"
urlpatterns = [
    path("me/", views.me, name="me"),
    path("team/", views.team, name="team"),
]
