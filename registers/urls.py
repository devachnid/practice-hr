from django.urls import path

from . import views

app_name = "registers"
urlpatterns = [
    path("<int:pk>/check/", views.check_now, name="check_now"),
]
