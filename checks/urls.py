from django.urls import path

from . import views

app_name = "checks"
urlpatterns = [
    path("<int:pk>/upload/", views.upload, name="upload"),
]
