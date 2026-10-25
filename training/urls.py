from django.urls import path

from . import views

app_name = "training"
urlpatterns = [
    path("record/", views.self_record, name="self_record"),
    path("session/", views.session, name="session"),
    path("records/<int:pk>/verify/", views.verify, name="verify"),
    path("records/<int:pk>/reject/", views.reject, name="reject"),
    path("<int:pk>/", views.person, name="person"),
    path("<int:pk>/record/", views.record, name="record"),
]
