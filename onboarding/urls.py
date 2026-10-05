from django.urls import path

from . import views

app_name = "onboarding"
urlpatterns = [
    path("", views.getting_started, name="getting_started"),
    path("details/", views.details, name="details"),
    path("item/<int:pk>/done/", views.complete, name="complete"),
    path("item/<int:pk>/not-needed/", views.not_needed, name="not_needed"),
    path("item/<int:pk>/remove/", views.remove_item, name="remove_item"),
    path("item/<int:pk>/upload/", views.upload, name="upload"),
    path("all/", views.hr_list, name="hr_list"),
    path("all/<int:pk>/", views.hr_detail, name="hr_detail"),
    path("all/<int:pk>/add/", views.add_item, name="add_item"),
]
