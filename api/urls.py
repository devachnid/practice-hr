from django.urls import path

from api import views

urlpatterns = [
    path("people", views.people, name="api-people"),
    path("patterns", views.patterns, name="api-patterns"),
    path("absences", views.absences, name="api-absences"),
]
