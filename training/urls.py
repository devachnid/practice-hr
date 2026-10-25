from django.urls import path

from . import views

app_name = "training"
urlpatterns = [
    path("record/", views.self_record, name="self_record"),
]
