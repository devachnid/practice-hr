from django.urls import path

from . import views

app_name = "documents"
urlpatterns = [
    path("file/<int:pk>/", views.download, name="download"),
]
